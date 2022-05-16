from __future__ import annotations

import numbers
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort

from bsmu.vision.core.bbox import BBox
from bsmu.vision.core.image import tile_splitter
from bsmu.vision.dnn.inferencer import Inferencer, preprocessed_image, padded_to_square_shape, padding_removed

if TYPE_CHECKING:
    from typing import Callable, List, Tuple, Sequence


def largest_connected_component_label(mask: np.ndarray) -> Tuple[int | None, np.ndarray, BBox | None]:
    """
    Find a connected component with the largest area (exclude background label, which is 0)
    :param mask: mask to find connected components
    :return: Tuple[largest connected component label, labeled mask, largest connected component bbox]
    If all pixels are background (zeros), then return None as the largest connected component label
    """

    assert mask.dtype == np.uint8, 'The mask must have np.uint8 type'

    labels_qty, labeled_mask, stats_by_component_label, centroids = cv.connectedComponentsWithStats(mask)
    largest_area = 0
    label_with_largest_area = None
    for label in range(1, labels_qty):
        label_area = stats_by_component_label[label, cv.CC_STAT_AREA]
        if label_area > largest_area:
            largest_area = label_area
            label_with_largest_area = label
    if label_with_largest_area is None:
        largest_component_bbox = None
    else:
        largest_component_stats_array = stats_by_component_label[label_with_largest_area]
        largest_component_left = largest_component_stats_array[cv.CC_STAT_LEFT]
        largest_component_top = largest_component_stats_array[cv.CC_STAT_TOP]
        largest_component_bbox = BBox(
            largest_component_left,
            largest_component_left + largest_component_stats_array[cv.CC_STAT_WIDTH],
            largest_component_top,
            largest_component_top + largest_component_stats_array[cv.CC_STAT_HEIGHT],
        )
    return label_with_largest_area, labeled_mask, largest_component_bbox


class Segmenter(Inferencer):
    def _segment_batch_without_postresize(self, images: Sequence[np.ndarray]) -> Sequence[np.ndarray]:
        input_image_batch = []

        for image in images:
            # If it's an RGBA-image
            if image.shape[2] == 4:
                # Remove alpha-channel
                image = image[:, :, :3]

            if image.shape[:2] != self._model_params.input_image_size:
                image = cv.resize(image, self._model_params.input_image_size, interpolation=cv.INTER_AREA)

            image = preprocessed_image(image, normalize=True, preprocessing_mode=self._model_params.preprocessing_mode)

            input_image_batch.append(image)

        self._create_inference_session()
        model_inputs: List[ort.NodeArg] = self._inference_session.get_inputs()
        assert len(model_inputs) == 1, 'Segmenter can process only models with one input'
        input_feed = {model_inputs[0].name: input_image_batch}
        model_outputs: List[ort.NodeArg] = self._inference_session.get_outputs()
        output_names = [model_output.name for model_output in model_outputs]
        outputs = self._inference_session.run(output_names, input_feed)
        assert len(outputs) == 1, 'Segmenter can process only models with one output'
        output_mask_batch = outputs[0]

        # Squeeze channels axis
        output_mask_batch = np.squeeze(output_mask_batch, axis=3)
        return output_mask_batch

    def _segment_without_postresize(self, image: np.ndarray) -> np.ndarray:
        return self._segment_batch_without_postresize([image])[0]

    def segment(
            self,
            image: np.ndarray,
            postprocessing: Callable[[np.ndarray], np.ndarray | Tuple] | None = None
    ) -> np.ndarray:
        mask = self._segment_without_postresize(image)

        if postprocessing is not None:
            postprocessing_result = postprocessing(mask)
            if isinstance(postprocessing_result, tuple):
                mask = postprocessing_result[0]
            else:
                mask = postprocessing_result

        src_image_shape = image.shape
        mask = cv.resize(mask, (src_image_shape[1], src_image_shape[0]), interpolation=cv.INTER_LINEAR_EXACT)

        return mask

    def segment_largest_connected_component_and_return_mask_with_bbox(
            self, image: np.ndarray, use_square_image: bool = True) -> Tuple[np.ndarray, BBox]:
        src_image_shape = image.shape

        if use_square_image:
            image, padding = padded_to_square_shape(image)

        image_shape_before_preresize = image.shape
        mask = self._segment_without_postresize(image)
        mask, largest_component_bbox = largest_connected_component_mask(mask)

        resize_factor_x = image_shape_before_preresize[1] / mask.shape[1]
        resize_factor_y = image_shape_before_preresize[0] / mask.shape[0]

        mask = cv.resize(
            mask,
            (image_shape_before_preresize[1], image_shape_before_preresize[0]),
            interpolation=cv.INTER_NEAREST_EXACT
        )

        if use_square_image:
            mask = padding_removed(mask, padding)

        if largest_component_bbox is not None:
            largest_component_bbox.resize(resize_factor_x, resize_factor_y)

            if use_square_image:
                largest_component_bbox.move_left(padding.left)
                largest_component_bbox.move_top(padding.top)

            largest_component_bbox.clip_to_shape(src_image_shape)

        return mask, largest_component_bbox

    def segment_largest_connected_component_and_return_mask_with_bbox_async(
            self,
            callback: Callable,
            image: np.ndarray,
            use_square_image: bool = True,
    ):
        self._call_async_with_callback(
            callback,
            self.segment_largest_connected_component_and_return_mask_with_bbox,
            image,
            use_square_image,
        )

    def segment_on_splitted_into_tiles(
            self,
            image: np.ndarray,
            use_square_image: bool = True,
            tile_grid_shape: Sequence = (3, 3),
            border_size: int = 10,
    ) -> np.ndarray:
        model_input_image_size = self._model_params.input_image_size
        borders_size = 2 * border_size
        model_input_image_size_multiplied_by_tile_shape = (
            (model_input_image_size[0] - borders_size) * tile_grid_shape[0],
            (model_input_image_size[1] - borders_size) * tile_grid_shape[1])

        if use_square_image:
            image, padding = padded_to_square_shape(image)

        image_shape_before_preresize = image.shape
        image = cv.resize(image, model_input_image_size_multiplied_by_tile_shape, interpolation=cv.INTER_AREA)

        # Split image into tiles
        image_tiles = tile_splitter.split_image_into_tiles(image, tile_grid_shape, border_size=border_size)
        # Get mask predictions for tiles
        tile_masks = self._segment_batch_without_postresize(image_tiles)
        # Merge tiles
        mask = tile_splitter.merge_tiles_into_image_with_blending(tile_masks, tile_grid_shape, border_size=border_size)

        # Resize resulted mask to image size
        mask = cv.resize(
            mask, (image_shape_before_preresize[1], image_shape_before_preresize[0]),
            interpolation=cv.INTER_LINEAR_EXACT)

        if use_square_image:
            mask = padding_removed(mask, padding)

        return mask

    def segment_on_splitted_into_tiles_async(
            self,
            callback: Callable,
            image: np.ndarray,
            use_square_image: bool = True,
            tile_grid_shape: Sequence = (3, 3),
            border_size: int = 10,
    ):
        self._call_async_with_callback(
            callback,
            self.segment_on_splitted_into_tiles,
            image,
            use_square_image,
            tile_grid_shape,
            border_size,
        )


def largest_connected_component_soft_mask(soft_mask: np.ndarray) -> Tuple[np.ndarray, BBox]:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: Tuple[soft mask with only largest connected component, largest connected component bbox]
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask, largest_component_bbox = largest_connected_component_label(mask)
    soft_mask_with_largest_connected_component = soft_mask.copy()
    # Do not erase zero-pixels to get soft mask
    soft_mask_with_largest_connected_component[
        np.logical_and(labeled_mask != label_with_largest_area, labeled_mask != 0)] = 0
    return soft_mask_with_largest_connected_component, largest_component_bbox


def largest_connected_component_mask(soft_mask: np.ndarray) -> Tuple[np.ndarray, BBox]:
    """
    Erase all pixels, which do not belong to the largest connected component.
    :return: Tuple[binarized mask with only largest connected component, largest connected component bbox]
    """

    assert issubclass(soft_mask.dtype.type, numbers.Real), 'This function is created for soft mask processing.'

    mask = np.round(soft_mask).astype(np.uint8)
    label_with_largest_area, labeled_mask, largest_component_bbox = largest_connected_component_label(mask)
    mask[labeled_mask != label_with_largest_area] = 0
    return mask, largest_component_bbox
