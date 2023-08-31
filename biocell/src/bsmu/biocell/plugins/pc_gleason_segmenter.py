from __future__ import annotations

from timeit import default_timer as timer
from typing import TYPE_CHECKING

import numpy as np
import skimage.io
import skimage.util
from PySide6.QtCore import QObject

from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from typing import Sequence
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class BiocellPcGleasonSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_loading_manager_plugin':
            'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
        'data_visualization_manager_plugin':
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin'
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
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

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._pc_gleason_3_segmenter: BiocellPcGleasonSegmenter | None = None
        self._pc_gleason_4_segmenter: BiocellPcGleasonSegmenter | None = None

    @property
    def pc_gleason_segmenter(self) -> BiocellPcGleasonSegmenter | None:
        return self._pc_gleason_3_segmenter

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager
        self._palette_pack_settings = self._palette_pack_settings_plugin.settings

        model_params_gleason_3 = DnnModelParams.from_config(
            self.config.value('gleason-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        model_params_gleason_4 = DnnModelParams.from_config(
            self.config.value('gleason-4-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        self._pc_gleason_3_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager,
            model_params_gleason_3,
            self._palette_pack_settings.main_palette,
            'gleason_3',
        )
        self._pc_gleason_4_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager,
            model_params_gleason_4,
            self._palette_pack_settings.main_palette,
            'gleason_4',
        )

        # self._data_visualization_manager.data_visualized.connect(self._pc_gleason_3_segmenter.on_data_visualized)

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        # self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Prostate Tissue', self._segment_prostate_tissue)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Cancer', self._segment_cancer)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Cancer - x4 Passes', self._segment_cancer_x4_passes)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Gleason >= 3', self._segment_gleason_3_and_above)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Gleason >= 4', self._segment_gleason_4_and_above)

    def _disable(self):
        self._pc_gleason_3_segmenter = None
        self._pc_gleason_4_segmenter = None

        self._file_loading_manager = None
        self._data_visualization_manager = None

        raise NotImplementedError

    def _active_layered_image(self) -> LayeredImage | None:
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        return layered_image_viewer_sub_window and layered_image_viewer_sub_window.layered_image_viewer.data

    def _segment_gleason_3_and_above(self):
        layered_image = self._active_layered_image()
        if layered_image is not None:
            self._pc_gleason_3_segmenter.segment(layered_image, 'gleason >= 3')

    def _segment_gleason_4_and_above(self):
        layered_image = self._active_layered_image()
        if layered_image is not None:
            self._pc_gleason_4_segmenter.segment(layered_image, 'gleason >= 4')

    def _segment_cancer(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        masks_layer_name = 'masks'
        self._pc_gleason_4_segmenter.segment(layered_image, masks_layer_name, repaint_full_mask=False)
        self._pc_gleason_3_segmenter.segment(layered_image, masks_layer_name, repaint_full_mask=False)

    def _segment_cancer_x4_passes(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        masks_layer_name = 'masks'
        self._pc_gleason_4_segmenter.segment(layered_image, masks_layer_name, repaint_full_mask=False, pass_count=4)
        self._pc_gleason_3_segmenter.segment(layered_image, masks_layer_name, repaint_full_mask=False, pass_count=4)

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
            Visibility(True, 0.5))


def segment_tissue(image: np.ndarray) -> np.ndarray:
    var = image - image.mean(-1, dtype=np.int16, keepdims=True)
    var = abs(var).mean(-1, dtype=np.uint16)
    tissue_mask = np.where(var > 2, True, False).astype(np.uint8)
    return tissue_mask


class BiocellPcGleasonSegmenter(QObject):
    def __init__(
            self,
            data_visualization_manager: DataVisualizationManager,
            model_params: DnnModelParams,
            mask_palette: Palette,
            palette_class_name: str = 'foreground',
    ):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._model_params = model_params
        self._mask_palette = mask_palette
        self._mask_class = self._mask_palette.row_index_by_name(palette_class_name)

        self._segmenter = DnnSegmenter(self._model_params)

        self._background_class = self._mask_palette.row_index_by_name('background')
        self._unknown_class = self._mask_palette.row_index_by_name('unknown')

    @property
    def tile_size(self) -> int:
        return self._model_params.input_image_size[0]

    def segment(
            self,
            layered_image: LayeredImage,
            mask_layer_name: str,
            repaint_full_mask: bool = True,
            threshold: float | None = 0,
            pass_count: int = 1,
    ):
        image = layered_image.layers[0].image.pixels

        match pass_count:
            case 1:
                mask, _ = self._segment_image(image, threshold=threshold)
            case 4:
                tile_weights = self._tile_weights(self.tile_size)

                weighted_mask = None
                weight_sum = None
                extra_pads_list = [(0, 0), (1, 1), (1, 0), (0, 1)]
                for extra_pads in extra_pads_list:
                    mask, mask_weights = self._segment_image(
                        image, extra_pads=extra_pads, threshold=None, tile_weights=tile_weights)
                    if weighted_mask is None:
                        weighted_mask = mask * mask_weights
                        weight_sum = mask_weights
                    else:
                        weighted_mask += mask * mask_weights
                        weight_sum += mask_weights
                # |weight_sum| is not always identity matrix (some pixels can have other values),
                # so we divide |weighted_mask| by |weight_sum|.
                # It's important, that all elements of |weight_sum| are not equal to zero,
                # else we will get division by zero.
                mask = weighted_mask / weight_sum

                mask = (mask > threshold).astype(np.uint8)
            case _:
                raise ValueError(f'|pass_count| with value {pass_count} is unimplemented')

        mask *= self._mask_class

        mask_layer = layered_image.layer_by_name(mask_layer_name)
        if repaint_full_mask or mask_layer is None or not mask_layer.is_image_pixels_valid:
            layered_image.add_layer_or_modify_pixels(
                mask_layer_name,
                mask,
                FlatImage,
                self._mask_palette,
                Visibility(True, 0.5))
        else:
            # If there is mask, repaint only over |background| and |unknown| classes
            repainting_mask = \
                (mask_layer.image_pixels == self._background_class) | (mask_layer.image_pixels == self._unknown_class)
            mask_layer.image_pixels[repainting_mask] = mask[repainting_mask]
            mask_layer.image.emit_pixels_modified()

    def on_data_visualized(self, data: Data, data_viewer_sub_windows: list[DataViewerSubWindow]):
        if not isinstance(data, LayeredImage) or (len(data.layers) > 1 and data.layers[1].name == 'mask'):
            return

        image = data.layers[0].image.pixels
        print('image:', image.shape, image.dtype, image.min(), image.max())

        mask = self._segment_image(image)
        data.add_layer_from_image(
            FlatImage(mask, Palette.default_binary(rgb_color=[0, 255, 0])),
            'mask',
            Visibility(True, 0.5))

    def _segment_image(
            self,
            image: np.ndarray,
            extra_pads: Sequence[float] = (0, 0),
            threshold: float | None = 0,
            tile_weights: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        print(f'Segment image using {self._model_params.path.name} model with {extra_pads} extra pads')
        segment_image_start = timer()

        # Remove alpha-channel
        if image.shape[2] == 4:
            image = image[..., :3]

        tile_size = self.tile_size
        padded_image, pads = self._padded_image_to_tile(image, tile_size, extra_pads=extra_pads)
        padded_mask = np.zeros(shape=padded_image.shape[:-1], dtype=np.float32)

        tiled_image = self._tiled_image(padded_image, tile_size)

        for tile_row in range(tiled_image.shape[0]):
            for tile_col in range(tiled_image.shape[1]):
                tile = tiled_image[tile_row, tile_col]
                tile_mask = self._segmenter.segment(tile)

                row = tile_row * tile_size
                col = tile_col * tile_size
                padded_mask[row:(row + tile_size), col:(col + tile_size)] = tile_mask

        mask = self._unpad_image(padded_mask, pads)

        weights = None
        if tile_weights is not None:
            padded_weights = np.tile(tile_weights, reps=(tiled_image.shape[:2]))
            weights = self._unpad_image(padded_weights, pads)

        if threshold is not None:
            mask = (mask > threshold).astype(np.uint8)

        print(f'\tElapsed time: {timer() - segment_image_start}')
        return mask, weights

    @staticmethod
    def _tiled_image(image: np.ndarray, tile_size: int) -> np.ndarray:
        tile_shape = (tile_size, tile_size, image.shape[-1])
        tiled = skimage.util.view_as_blocks(image, tile_shape)
        return tiled.squeeze(axis=2)

    @staticmethod
    def _padded_image_to_tile(image: np.ndarray, tile_size: int, extra_pads: Sequence[float] = (0, 0), pad_value=255) \
            -> tuple[np.ndarray, tuple]:
        """
        Returns a padded |image| so that its dimensions are evenly divisible by the |tile_size|
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
               pads[1][0]:image.shape[1] - pads[1][1]]

    @staticmethod
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
