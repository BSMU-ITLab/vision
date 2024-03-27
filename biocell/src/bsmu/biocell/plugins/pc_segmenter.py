from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from timeit import default_timer as timer
from typing import TYPE_CHECKING

import numpy as np
import skimage.io
import skimage.util
from PySide6.QtCore import QObject

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.task import DnnTask
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter

if TYPE_CHECKING:
    from typing import Callable, Sequence
    from bsmu.vision.core.image.base import Image
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin
    from bsmu.vision.plugins.storages import TaskStorage, TaskStoragePlugin


class SegmentationMode(Enum):
    HIGH_QUALITY = 1
    FAST = 2

    @property
    def display_name(self) -> str:
        return _SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME[self].display_name

    @property
    def display_name_with_postfix(self) -> str:
        return f'{self.display_name} Segmentation'

    @property
    def short_name(self) -> str:
        return _SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME[self].short_name

    @property
    def short_name_with_postfix(self) -> str:
        return f'{self.short_name}-Seg'


@dataclass
class DisplayShortName:
    display_name: str
    short_name: str


_SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME = {
    SegmentationMode.HIGH_QUALITY: DisplayShortName('High-Quality', 'HQ'),
    SegmentationMode.FAST: DisplayShortName('Fast', 'F'),
}


class PcSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            task_storage_plugin: TaskStoragePlugin,
    ):
        super().__init__()

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._task_storage_plugin = task_storage_plugin

        self._pc_gleason_3_segmenter: PcGleasonSegmenter | None = None
        self._pc_gleason_4_segmenter: PcGleasonSegmenter | None = None

        self._pc_segmenter: PcSegmenter | None = None

    @property
    def pc_gleason_3_segmenter(self) -> PcGleasonSegmenter | None:
        return self._pc_gleason_3_segmenter

    @property
    def pc_gleason_4_segmenter(self) -> PcGleasonSegmenter | None:
        return self._pc_gleason_4_segmenter

    @property
    def pc_segmenter(self) -> PcSegmenter | None:
        return self._pc_segmenter

    def _enable(self):
        gleason_3_model_params = DnnModelParams.from_config(
            self.config_value('gleason_3_segmenter_model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        gleason_4_model_params = DnnModelParams.from_config(
            self.config_value('gleason_4_segmenter_model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        main_palette = self._palette_pack_settings_plugin.settings.main_palette
        task_storage = self._task_storage_plugin.task_storage
        self._pc_gleason_3_segmenter = PcGleasonSegmenter(
            gleason_3_model_params, main_palette, 'gleason_3', task_storage)
        self._pc_gleason_4_segmenter = PcGleasonSegmenter(
            gleason_4_model_params, main_palette, 'gleason_4', task_storage)
        self._pc_segmenter = PcSegmenter(
            [self._pc_gleason_3_segmenter, self._pc_gleason_4_segmenter],
            task_storage,
        )

    def _disable(self):
        self._pc_segmenter = None
        self._pc_gleason_3_segmenter = None
        self._pc_gleason_4_segmenter = None


class PcSegmenter(QObject):
    def __init__(self, class_segmenters: Sequence[PcGleasonSegmenter], task_storage: TaskStorage = None):
        super().__init__()

        self._class_segmenters = class_segmenters
        self._task_storage = task_storage

    def segment_async(
            self,
            image: Image,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY,
            on_finished: Callable[[Sequence[np.ndarray]], None] | None = None,
    ):
        pc_segmentation_task = self.create_segmentation_task(image, segmentation_mode)
        pc_segmentation_task.on_finished = on_finished

        if self._task_storage is not None:
            self._task_storage.add_item(pc_segmentation_task)
        ThreadPool.run_async_task(pc_segmentation_task)

    def create_segmentation_task(
            self,
            image: Image,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY
    ) -> MulticlassMultipassTiledSegmentationTask:

        segmentation_profiles = []
        for class_segmenter in self._class_segmenters:
            segmentation_profiles.append(
                MultipassTiledSegmentationProfile(
                    class_segmenter.segmenter,
                    segmentation_mode,
                    class_segmenter.mask_background_class,
                    class_segmenter.mask_foreground_class,
                )
            )
        pc_segmentation_task_name = f'PC {segmentation_mode.short_name_with_postfix} [{image.path_name}]'
        return MulticlassMultipassTiledSegmentationTask(image.pixels, segmentation_profiles, pc_segmentation_task_name)

    def combine_class_masks(self, class_masks: Sequence[np.ndarray]) -> np.ndarray:
        combined_mask = class_masks[0].copy()
        # Skip first elements, because the `combined_mask` already contains the first mask
        for class_mask, class_segmenter in zip(class_masks[1:], self._class_segmenters[1:]):
            is_foreground_class = class_mask == class_segmenter.mask_foreground_class
            combined_mask[is_foreground_class] = class_segmenter.mask_foreground_class
        return combined_mask


class PcGleasonSegmenter(QObject):
    def __init__(
            self,
            model_params: DnnModelParams,
            mask_palette: Palette,
            mask_foreground_class_name: str = 'foreground',
            task_storage: TaskStorage = None,
    ):
        super().__init__()

        self._model_params = model_params
        self._task_storage = task_storage

        self._mask_background_class = mask_palette.row_index_by_name('background')
        self._mask_foreground_class = mask_palette.row_index_by_name(mask_foreground_class_name)

        self._segmenter = DnnSegmenter(self._model_params)

    @property
    def segmenter(self) -> DnnSegmenter:
        return self._segmenter

    @property
    def mask_background_class(self) -> int:
        return self._mask_background_class

    @property
    def mask_foreground_class(self) -> int:
        return self._mask_foreground_class

    def segment_async(
            self,
            image: Image,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY,
            on_finished: Callable[[np.ndarray], None] | None = None,
    ):
        segmentation_profile = MultipassTiledSegmentationProfile(
            self._segmenter, segmentation_mode, self._mask_background_class, self._mask_foreground_class)
        pc_gleason_segmentation_task_name = (
            f'PC {self._model_params.output_object_short_name} '
            f'{segmentation_mode.short_name_with_postfix} '
            f'[{image.path_name}]'
        )
        pc_gleason_segmentation_task = MultipassTiledSegmentationTask(
            image.pixels,
            segmentation_profile,
            pc_gleason_segmentation_task_name,
        )
        pc_gleason_segmentation_task.on_finished = on_finished

        if self._task_storage is not None:
            self._task_storage.add_item(pc_gleason_segmentation_task)
        ThreadPool.run_async_task(pc_gleason_segmentation_task)


class TiledSegmentationTask(DnnTask):
    def __init__(
            self,
            image: np.ndarray,
            segmenter: DnnSegmenter,
            extra_pads: Sequence[float] = (0, 0),
            binarize_mask: bool = True,
            mask_background_class: int = 0,
            mask_foreground_class: int = 1,
            tile_weights: np.ndarray | None = None,
            name: str = '',
    ):
        super().__init__(name)

        self._image = image
        self._segmenter = segmenter
        self._extra_pads = extra_pads
        self._binarize_mask = binarize_mask
        self._mask_background_class = mask_background_class
        self._mask_foreground_class = mask_foreground_class
        self._tile_weights = tile_weights

    @property
    def model_params(self) -> DnnModelParams:
        return self._segmenter.model_params

    @property
    def tile_size(self) -> int:
        return self.model_params.input_image_size[0]

    def _run(self) -> tuple[np.ndarray, np.ndarray]:
        return self._segment_tiled()

    def _segment_tiled(self) -> tuple[np.ndarray, np.ndarray]:
        logging.info(f'Segment image using {self.model_params.path.name} model with {self._extra_pads} extra pads')
        segmentation_start = timer()

        image = self._image
        # Remove alpha-channel
        if image.shape[2] == 4:
            image = image[..., :3]

        tile_size = self.tile_size
        padded_image, pads = self._padded_image_to_tile(image, tile_size, extra_pads=self._extra_pads)
        # Create a mask filled with `self._mask_background_class`, because this Task can be cancelled, and then
        # we have to return correct partial mask
        padded_mask = np.full(shape=padded_image.shape[:-1], fill_value=self._mask_background_class, dtype=np.float32)

        tiled_image = self._tiled_image(padded_image, tile_size)

        tile_row_count = tiled_image.shape[0]
        tile_col_count = tiled_image.shape[1]
        total_tile_count = tile_row_count * tile_col_count
        segmented_tile_count = 0
        for tile_row in range(tile_row_count):
            for tile_col in range(tile_col_count):
                # if self._is_cancelled:
                #     return mask, weights

                tile = tiled_image[tile_row, tile_col]
                tile_mask = self._segmenter.segment(tile)

                row = tile_row * tile_size
                col = tile_col * tile_size
                padded_mask[row:(row + tile_size), col:(col + tile_size)] = tile_mask

                segmented_tile_count += 1
                self._change_step_progress(segmented_tile_count, total_tile_count)

        mask = self._unpad_image(padded_mask, pads)

        weights = None
        if self._tile_weights is not None:
            padded_weights = np.tile(self._tile_weights, reps=(tiled_image.shape[:2]))
            weights = self._unpad_image(padded_weights, pads)

        if self._binarize_mask:
            mask = (mask > self.model_params.mask_binarization_threshold).astype(np.uint8)
            mask *= self._mask_foreground_class

        logging.info(f'Segmentation finished. Elapsed time: {timer() - segmentation_start:.2f}')
        return mask, weights

    @staticmethod
    def _padded_image_to_tile(
            image: np.ndarray,
            tile_size: int,
            extra_pads: Sequence[float] = (0, 0),
            pad_value=255
    ) -> tuple[np.ndarray, tuple]:
        """
        Returns a padded |image| so that its dimensions are evenly divisible by the |tile_size| and pads
        :param extra_pads: additionally adds the |tile_size| multiplied by |extra_pads| to get shifted tiles
        """
        rows, cols, channels = image.shape

        pad_rows = (-rows % tile_size) + extra_pads[0] * tile_size
        pad_cols = (-cols % tile_size) + extra_pads[1] * tile_size

        pad_rows_half = pad_rows // 2
        pad_cols_half = pad_cols // 2

        pads = ((pad_rows_half, pad_rows - pad_rows_half), (pad_cols_half, pad_cols - pad_cols_half), (0, 0))
        image = np.pad(image, pads, constant_values=pad_value)
        return image, pads

    @staticmethod
    def _unpad_image(image: np.ndarray, pads: tuple) -> np.ndarray:
        return image[
               pads[0][0]:image.shape[0] - pads[0][1],
               pads[1][0]:image.shape[1] - pads[1][1],
               ]

    @staticmethod
    def _tiled_image(image: np.ndarray, tile_size: int) -> np.ndarray:
        tile_shape = (tile_size, tile_size, image.shape[-1])
        tiled = skimage.util.view_as_blocks(image, tile_shape)
        return tiled.squeeze(axis=2)


class MultipassTiledSegmentationTask(DnnTask):
    def __init__(
            self,
            image: np.ndarray,
            segmentation_profile: MultipassTiledSegmentationProfile,
            name: str = '',
    ):
        super().__init__(name)

        self._image = image
        self._segmentation_profile = segmentation_profile

        self._finished_subtask_count = 0

    def _run(self) -> np.ndarray:
        return self._segment_multipass_tiled()

    def _segment_multipass_tiled(self) -> np.ndarray:
        assert self._segmentation_profile.extra_pads_sequence, '`extra_pads_sequence` should not be empty'

        mask = None
        weighted_mask = None
        weight_sum = None
        for self._finished_subtask_count, extra_pads in enumerate(self._segmentation_profile.extra_pads_sequence):
            tiled_segmentation_task = TiledSegmentationTask(
                self._image,
                self._segmentation_profile.segmenter,
                extra_pads,
                False,
                self._segmentation_profile.mask_background_class,
                self._segmentation_profile.mask_foreground_class,
                self._segmentation_profile.tile_weights,
            )
            tiled_segmentation_task.progress_changed.connect(self._on_segmentation_subtask_progress_changed)
            tiled_segmentation_task.run()
            mask, mask_weights = tiled_segmentation_task.result
            if len(self._segmentation_profile.extra_pads_sequence) > 1:
                if weighted_mask is None:
                    weighted_mask = mask * mask_weights
                    weight_sum = mask_weights
                else:
                    weighted_mask += mask * mask_weights
                    weight_sum += mask_weights

        # `weight_sum` accumulates the sum of weights for each pixel across all masks.
        # When dividing `weighted_mask` by `weight_sum`, we normalize the mask values.
        # It's essential that no element in `weight_sum` is zero to prevent division by zero errors.
        if weighted_mask is not None:
            mask = weighted_mask / weight_sum

        mask = (mask > self._segmentation_profile.mask_binarization_threshold).astype(np.uint8)
        mask *= self._segmentation_profile.mask_foreground_class

        return mask

    def _on_segmentation_subtask_progress_changed(self, progress: float):
        self._change_subtask_based_progress(
            self._finished_subtask_count, len(self._segmentation_profile.extra_pads_sequence), progress)


def _tile_weights(tile_size: int) -> np.ndarray:
    """
    Returns tile weights, where maximum weights (equal to 1) are in the center of the tile,
    and the weights gradually decreases to zero towards the edges of the tile
    E.g.: |tile_size| is equal to 6:
    np.array([[0. , 0. , 0. , 0. , 0. , 0. ],
              [0. , 0.5, 0.5, 0.5, 0.5, 0. ],
              [0. , 0.5, 1. , 1. , 0.5, 0. ],
              [0. , 0.5, 1. , 1. , 0.5, 0. ],
              [0. , 0.5, 0.5, 0.5, 0.5, 0. ],
              [0. , 0. , 0. , 0. , 0. , 0. ]], dtype=float16)
    """
    assert tile_size % 2 == 0, 'Current method version can work only with even tile size'
    max_int_weight = (tile_size // 2) - 1
    int_weights = list(range(max_int_weight + 1))
    int_weights = int_weights + int_weights[::-1]
    row_int_weights = np.expand_dims(int_weights, 0)
    col_int_weights = np.expand_dims(int_weights, 1)
    tile_int_weights = np.minimum(row_int_weights, col_int_weights)
    return (tile_int_weights / max_int_weight).astype(np.float16)


@dataclass
class MultipassTiledSegmentationProfile:
    segmenter: DnnSegmenter
    segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY
    mask_background_class: int = 0
    mask_foreground_class: int = 1
    tile_weights: np.ndarray | None = None

    def __post_init__(self):
        if self.tile_weights is None:
            self.tile_weights = _tile_weights(self.tile_size)

    @property
    def extra_pads_sequence(self) -> Sequence[Sequence[float]]:
        return ([(0, 0), (1, 1), (1, 0), (0, 1)]
                if self.segmentation_mode is SegmentationMode.HIGH_QUALITY
                else [(0, 0)])

    @property
    def tile_size(self) -> int:
        return self.segmenter.model_params.input_image_size[0]

    @property
    def mask_binarization_threshold(self) -> float:
        return self.segmenter.model_params.mask_binarization_threshold


class MulticlassMultipassTiledSegmentationTask(DnnTask):
    def __init__(
            self,
            image: np.ndarray,
            segmentation_profiles: Sequence[MultipassTiledSegmentationProfile],
            name: str = '',
    ):
        super().__init__(name)

        self._image = image
        self._segmentation_profiles = segmentation_profiles

        self._finished_subtask_count = 0

    def _run(self) -> Sequence[np.ndarray]:
        return self._segment_multiclass_multipass_tiled()

    def _segment_multiclass_multipass_tiled(self) -> Sequence[np.ndarray]:
        masks = []
        for self._finished_subtask_count, segmentation_profile in enumerate(self._segmentation_profiles):
            tiled_segmentation_task = MultipassTiledSegmentationTask(self._image, segmentation_profile)
            tiled_segmentation_task.progress_changed.connect(self._on_segmentation_subtask_progress_changed)
            tiled_segmentation_task.run()
            mask = tiled_segmentation_task.result
            masks.append(mask)
        return masks

    def _on_segmentation_subtask_progress_changed(self, progress: float):
        self._change_subtask_based_progress(self._finished_subtask_count, len(self._segmentation_profiles), progress)
