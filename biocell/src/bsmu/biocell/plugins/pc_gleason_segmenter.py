from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from functools import partial
from timeit import default_timer as timer
from typing import TYPE_CHECKING

import numpy as np
import skimage.io
import skimage.util
from PySide6.QtCore import QObject

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.task import DnnTask
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from typing import Sequence, Any, Callable
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.storages import TaskStorage, TaskStoragePlugin
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class SegmentationMode(Enum):
    HIGH_QUALITY_SEGMENTATION = 1
    FAST_SEGMENTATION = 2

    @property
    def display_name(self) -> str:
        return _SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME[self].display_name

    @property
    def short_name(self) -> str:
        return _SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME[self].short_name


@dataclass
class DisplayShortName:
    display_name: str
    short_name: str


_SEGMENTATION_MODE_TO_DISPLAY_SHORT_NAME = {
    SegmentationMode.HIGH_QUALITY_SEGMENTATION: DisplayShortName('High-Quality Segmentation', 'HQ-Seg'),
    SegmentationMode.FAST_SEGMENTATION: DisplayShortName('Fast Segmentation', 'F-Seg'),
}


class BiocellPcGleasonSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_loading_manager_plugin':
            'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
        'data_visualization_manager_plugin':
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
            task_storage_plugin: TaskStoragePlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager

        self._task_storage_plugin = task_storage_plugin

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._pc_gleason_3_segmenter: BiocellPcGleasonSegmenter | None = None
        self._pc_gleason_4_segmenter: BiocellPcGleasonSegmenter | None = None

        self._pc_segmenter: BiocellPcSegmenter | None = None

    @property
    def pc_gleason_3_segmenter(self) -> BiocellPcGleasonSegmenter | None:
        return self._pc_gleason_3_segmenter

    @property
    def pc_gleason_4_segmenter(self) -> BiocellPcGleasonSegmenter | None:
        return self._pc_gleason_4_segmenter

    @property
    def pc_segmenter(self) -> BiocellPcSegmenter | None:
        return self._pc_segmenter

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._palette_pack_settings = self._palette_pack_settings_plugin.settings

        model_params_gleason_3 = DnnModelParams.from_config(
            self.config.value('gleason_3_segmenter_model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        model_params_gleason_4 = DnnModelParams.from_config(
            self.config.value('gleason_4_segmenter_model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        main_palette = self._palette_pack_settings.main_palette
        task_storage = self._task_storage_plugin.task_storage
        self._pc_gleason_3_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager,
            model_params_gleason_3,
            main_palette,
            'gleason_3',
            task_storage,
        )
        self._pc_gleason_4_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager,
            model_params_gleason_4,
            main_palette,
            'gleason_4',
            task_storage,
        )
        self._pc_segmenter = BiocellPcSegmenter(
            [self._pc_gleason_4_segmenter, self._pc_gleason_3_segmenter],
            task_storage,
        )

        # self._data_visualization_manager.data_visualized.connect(self._pc_gleason_3_segmenter.on_data_visualized)

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        # self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Prostate Tissue', self._segment_prostate_tissue)

        self._add_segmentation_submenu('Segment Cancer', self._segment_cancer)
        self._add_segmentation_submenu('Segment Gleason >= 3', self._segment_gleason_3_and_above)
        self._add_segmentation_submenu('Segment Gleason >= 4', self._segment_gleason_4_and_above)

    def _disable(self):
        self._pc_segmenter = None
        self._pc_gleason_3_segmenter = None
        self._pc_gleason_4_segmenter = None

        self._file_loading_manager = None
        self._data_visualization_manager = None
        self._palette_pack_settings = None

        raise NotImplementedError

    def _add_segmentation_submenu(self, title: str, method: Callable):
        submenu = self._main_window.add_submenu(AlgorithmsMenu, title)
        for segmentation_mode in SegmentationMode:
            submenu.addAction(segmentation_mode.display_name, partial(method, segmentation_mode))

    def _active_layered_image(self) -> LayeredImage | None:
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        return layered_image_viewer_sub_window and layered_image_viewer_sub_window.layered_image_viewer.data

    def _segment_gleason_3_and_above(
            self, segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION):
        layered_image = self._active_layered_image()
        if layered_image is not None:
            self._pc_gleason_3_segmenter.segment_async(
                layered_image, 'gleason >= 3', segmentation_mode=segmentation_mode)

    def _segment_gleason_4_and_above(
            self, segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION):
        layered_image = self._active_layered_image()
        if layered_image is not None:
            self._pc_gleason_4_segmenter.segment_async(
                layered_image, 'gleason >= 4', segmentation_mode=segmentation_mode)

    def _segment_cancer(self, segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        masks_layer_name = 'masks'
        self._pc_segmenter.segment_async(
            layered_image, masks_layer_name, repaint_full_mask=False, segmentation_mode=segmentation_mode)

    def _segment_prostate_tissue(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        tissue_layer_name = 'prostate-tissue'

        image = layered_image.layers[0].image.pixels
        tissue_mask = segment_tissue(image)
        print('Tissue mask: ', tissue_mask.dtype, tissue_mask.shape, tissue_mask.min(), tissue_mask.max(), np.unique(tissue_mask))
        layered_image.add_layer_or_modify_pixels(
            tissue_layer_name,
            tissue_mask,
            FlatImage,
            Palette.default_binary(rgb_color=[100, 255, 100]),
            Visibility(True, 0.5),
        )


def segment_tissue(image: np.ndarray) -> np.ndarray:
    var = image - image.mean(-1, dtype=np.int16, keepdims=True)
    var = abs(var).mean(-1, dtype=np.uint16)
    tissue_mask = np.where(var > 2, True, False).astype(np.uint8)
    return tissue_mask


class BiocellPcSegmenter(QObject):
    def __init__(self, class_segmenters: Sequence[BiocellPcGleasonSegmenter], task_storage: TaskStorage = None):
        super().__init__()

        self._class_segmenters = class_segmenters
        self._task_storage = task_storage

    def segment_async(
            self,
            layered_image: LayeredImage,
            mask_layer_name: str,
            repaint_full_mask: bool = True,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION,
    ):
        image_layer = layered_image.layers[0]
        image = image_layer.image.pixels

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

        pc_segmentation_task = MulticlassMultipassTiledSegmentationTask(
            segmentation_profiles, image, f'PC {segmentation_mode.short_name} [{image_layer.image_path.name}]')
        pc_segmentation_task.on_finished = partial(
            self._on_pc_segmentation_task_finished,
            layered_image=layered_image,
            mask_layer_name=mask_layer_name,
            repaint_full_mask=repaint_full_mask
        )

        if self._task_storage is not None:
            self._task_storage.add_item(pc_segmentation_task)
        ThreadPool.run_async_task(pc_segmentation_task)

    def _on_pc_segmentation_task_finished(
            self,
            masks: Sequence[np.ndarray],
            layered_image: LayeredImage,
            mask_layer_name: str,
            repaint_full_mask: bool
    ):
        for class_segmenter, mask in zip(self._class_segmenters, masks):
            class_segmenter.update_mask_layer(mask, layered_image, mask_layer_name, repaint_full_mask)


class BiocellPcGleasonSegmenter(QObject):
    def __init__(
            self,
            data_visualization_manager: DataVisualizationManager,
            model_params: DnnModelParams,
            mask_palette: Palette,
            mask_foreground_class_name: str = 'foreground',
            task_storage: TaskStorage = None,
    ):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._model_params = model_params
        self._mask_palette = mask_palette
        self._task_storage = task_storage

        self._mask_foreground_class = self._mask_palette.row_index_by_name(mask_foreground_class_name)
        self._mask_background_class = self._mask_palette.row_index_by_name('background')
        self._mask_unknown_class = self._mask_palette.row_index_by_name('unknown')

        self._segmenter = DnnSegmenter(self._model_params)

    @property
    def segmenter(self) -> DnnSegmenter:
        return self._segmenter

    @property
    def mask_foreground_class(self) -> int:
        return self._mask_foreground_class

    @property
    def mask_background_class(self) -> int:
        return self._mask_background_class

    def segment_async(
            self,
            layered_image: LayeredImage,
            mask_layer_name: str,
            repaint_full_mask: bool = True,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION,
    ):
        image_layer = layered_image.layers[0]
        image = image_layer.image.pixels

        pc_gleason_segmentation_task = MultipassTiledSegmentationTask(
            image,
            MultipassTiledSegmentationProfile(
                self._segmenter, segmentation_mode, self._mask_background_class, self._mask_foreground_class),
            name=f'PC {self._model_params.output_object_short_name} {segmentation_mode.short_name} '
                 f'[{image_layer.image_path.name}]'
        )
        pc_gleason_segmentation_task.on_finished = partial(
            self._on_pc_gleason_segmentation_task_finished,
            layered_image=layered_image,
            mask_layer_name=mask_layer_name,
            repaint_full_mask=repaint_full_mask,
        )
        if self._task_storage is not None:
            self._task_storage.add_item(pc_gleason_segmentation_task)
        ThreadPool.run_async_task(pc_gleason_segmentation_task)

    def _on_pc_gleason_segmentation_task_finished(
            self, mask: np.ndarray, layered_image: LayeredImage, mask_layer_name: str, repaint_full_mask: bool):
        self.update_mask_layer(mask, layered_image, mask_layer_name, repaint_full_mask)

    def update_mask_layer(
            self, mask: np.ndarray, layered_image: LayeredImage, mask_layer_name: str, repaint_full_mask: bool):
        mask *= self._mask_foreground_class
        mask_layer = layered_image.layer_by_name(mask_layer_name)
        if repaint_full_mask or mask_layer is None or not mask_layer.is_image_pixels_valid:
            layered_image.add_layer_or_modify_pixels(
                mask_layer_name,
                mask,
                FlatImage,
                self._mask_palette,
                Visibility(True, 0.5)
            )
        else:
            # If there is a mask, repaint only over `background` and `unknown` classes
            repainting_mask = (mask_layer.image_pixels == self._mask_background_class) \
                              | (mask_layer.image_pixels == self._mask_unknown_class)
            mask_layer.image_pixels[repainting_mask] = mask[repainting_mask]
            mask_layer.image.emit_pixels_modified()

    def on_data_visualized(self, data: Data, data_viewer_sub_windows: list[DataViewerSubWindow]):
        mask_layer_name = self._model_params.output_object_name
        if not isinstance(data, LayeredImage) or (len(data.layers) > 1 and data.layers[1].name == mask_layer_name):
            return

        self.segment_async(data, mask_layer_name)


class TiledSegmentationTask(DnnTask):
    def __init__(
            self,
            image: np.ndarray,
            segmenter: DnnSegmenter,
            extra_pads: Sequence[float] = (0, 0),
            mask_threshold: float | None = 0.5,
            mask_background_class: int = 0,
            mask_foreground_class: int = 1,
            tile_weights: np.ndarray | None = None,
            name: str = '',
    ):
        super().__init__(name)

        self._image = image
        self._segmenter = segmenter
        self._extra_pads = extra_pads
        self._mask_threshold = mask_threshold
        self._mask_background_class = mask_background_class
        self._mask_foreground_class = mask_foreground_class
        self._tile_weights = tile_weights

    @property
    def model_params(self) -> DnnModelParams:
        return self._segmenter.model_params

    @property
    def tile_size(self) -> int:
        return self.model_params.input_image_size[0]

    def _run(self) -> Any:
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

        if self._mask_threshold is not None:
            mask = (mask > self._mask_threshold).astype(np.uint8)

        logging.info(f'Segmentation finished. Elapsed time: {timer() - segmentation_start:.2f}')
        return mask, weights

    @staticmethod
    def _padded_image_to_tile(image: np.ndarray, tile_size: int, extra_pads: Sequence[float] = (0, 0), pad_value=255) \
            -> tuple[np.ndarray, tuple]:
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

    def _run(self) -> Any:
        return self._segment_multipass_tiled()

    def _segment_multipass_tiled(self):
        assert self._segmentation_profile.extra_pads_sequence, '`extra_pads_sequence` should not be empty'

        mask = None
        weighted_mask = None
        weight_sum = None
        for self._finished_subtask_count, extra_pads in enumerate(self._segmentation_profile.extra_pads_sequence):
            tiled_segmentation_task = TiledSegmentationTask(
                self._image,
                self._segmentation_profile.segmenter,
                extra_pads,
                None,
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

        return mask

    def _on_segmentation_subtask_progress_changed(self, progress: float):
        self.progress = (self._finished_subtask_count * 100 + progress) \
                        / len(self._segmentation_profile.extra_pads_sequence)


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
    segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY_SEGMENTATION
    mask_background_class: int = 0
    mask_foreground_class: int = 1
    tile_weights: np.ndarray | None = None

    def __post_init__(self):
        if self.tile_weights is None:
            self.tile_weights = _tile_weights(self.tile_size)

    @property
    def extra_pads_sequence(self) -> Sequence[Sequence[float]]:
        return [(0, 0), (1, 1), (1, 0), (0, 1)] \
            if self.segmentation_mode is SegmentationMode.HIGH_QUALITY_SEGMENTATION \
            else [(0, 0)]

    @property
    def tile_size(self) -> int:
        return self.segmenter.model_params.input_image_size[0]

    @property
    def mask_binarization_threshold(self) -> float:
        return self.segmenter.model_params.mask_binarization_threshold


class MulticlassMultipassTiledSegmentationTask(DnnTask):
    def __init__(
            self,
            segmentation_profiles: Sequence[MultipassTiledSegmentationProfile],
            image: np.ndarray,
            name: str = '',
    ):
        super().__init__(name)

        self._segmentation_profiles = segmentation_profiles
        self._image = image

        self._finished_subtask_count = 0

    def _run(self) -> Any:
        return self._segment_multiclass_multipass_tiled()

    def _segment_multiclass_multipass_tiled(self):
        masks = []
        for self._finished_subtask_count, segmentation_profile in enumerate(self._segmentation_profiles):
            tiled_segmentation_task = MultipassTiledSegmentationTask(self._image, segmentation_profile)
            tiled_segmentation_task.progress_changed.connect(self._on_segmentation_subtask_progress_changed)
            tiled_segmentation_task.run()
            mask = tiled_segmentation_task.result
            masks.append(mask)
        return masks

    def _on_segmentation_subtask_progress_changed(self, progress: float):
        self.progress = (self._finished_subtask_count * 100 + progress) / len(self._segmentation_profiles)
