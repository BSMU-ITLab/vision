from __future__ import annotations

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
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
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
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
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

        self._pc_gleason_3_segmenter: BiocellPcGleasonSegmenter | None = None
        self._pc_gleason_4_segmenter: BiocellPcGleasonSegmenter | None = None

    @property
    def pc_gleason_segmenter(self) -> BiocellPcGleasonSegmenter | None:
        return self._pc_gleason_3_segmenter

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        model_params_gleason_3 = DnnModelParams.from_config(
            self.config.value('gleason-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))
        model_params_gleason_4 = DnnModelParams.from_config(
            self.config.value('gleason-4-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        self._pc_gleason_3_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager, model_params_gleason_3, Palette.default_binary(rgb_color=[255, 255, 0]))
        self._pc_gleason_4_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager, model_params_gleason_4, Palette.default_binary(rgb_color=[255, 165, 0]))

        # self._data_visualization_manager.data_visualized.connect(self._pc_gleason_3_segmenter.on_data_visualized)

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Gleason >= 3', self._segment_gleason_3_and_above)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Gleason >= 4', self._segment_gleason_4_and_above)

    def _disable(self):
        self._pc_gleason_3_segmenter = None
        self._pc_gleason_4_segmenter = None

        self._file_loading_manager = None
        self._data_visualization_manager = None

        raise NotImplementedError

    def _segment_gleason_3_and_above(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        self._pc_gleason_3_segmenter.segment(layered_image_viewer.data, 'gleason >= 3')

    def _segment_gleason_4_and_above(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        self._pc_gleason_4_segmenter.segment(layered_image_viewer.data, 'gleason >= 4')


class BiocellPcGleasonSegmenter(QObject):
    def __init__(
            self, data_visualization_manager: DataVisualizationManager,
            model_params: DnnModelParams,
            mask_palette: Palette,
    ):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._model_params = model_params
        self._mask_palette = mask_palette

        self._segmenter = DnnSegmenter(self._model_params)

    def segment(self, layered_image: LayeredImage, mask_layer_name: str):
        print('segment', type(layered_image))

        image = layered_image.layers[0].image.pixels
        print('image:', image.shape, image.dtype, image.min(), image.max())

        mask = self._segment_image(image)
        layered_image.add_layer_or_modify_pixels(
            mask_layer_name,
            mask,
            FlatImage,
            self._mask_palette,
            Visibility(True, 0.5))

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

    def _segment_image(self, image: np.ndarray) -> np.ndarray:
        # Remove alpha-channel
        if image.shape[2] == 4:
            image = image[..., :3]

        tile_size = self._model_params.input_image_size[0]
        padded_image, pads = self._padded_image_to_tile(image, tile_size)
        tiled_image = self._tiled_image(padded_image, tile_size)
        print('padded_image:', padded_image.shape)
        print('tiled_image:', tiled_image.shape)

        # tiled_mask = np.zeros(shape=tiled_image.shape[:-1], dtype=np.uint8)
        # tiled_mask = tiled_mask.squeeze(2)

        # tiled_mask = np.zeros(
        #     shape=(tiled_image.shape[0], tiled_image.shape[1], tiled_image.shape[3], tiled_image.shape[4]),
        #     dtype=np.uint8)

        # tiled_mask = np.zeros(shape=padded_image.shape[:-1], dtype=np.uint8)
        # block_shape = (tile_size, tile_size)
        # tiled_mask = skimage.util.view_as_blocks(tiled_mask, block_shape)

        tiled_mask = np.zeros(shape=padded_image.shape[:-1], dtype=np.uint8)

        print('tiled_mask:', tiled_mask.shape)

        for row in range(tiled_image.shape[0]):
            for col in range(tiled_image.shape[1]):
                # print(f'ROW: {row}   COL:{col}')


                # if row != 3 or col != 15:
                #     continue


                tile = tiled_image[row, col, 0]
                # skimage.io.imsave(r'D:\Temp\gleason-segmentation-tests\tile.png', tile)

                # self._data_visualization_manager.visualize_data(FlatImage(tile, path=Path(f'{row}-{col}')))

                tile = tile.astype(np.float32)
                # tile = (255 - tile) / 255
                # tile = tile / 255

                tile_mask = self._segmenter.segment(tile)

                # tiled_mask[row, col] = tile_mask > 0.5

                tile_y = row * tile_size
                tile_x = col * tile_size
                tiled_mask[tile_y:(tile_y + tile_size), tile_x:(tile_x + tile_size)] = tile_mask > 0 #% 0.5

        # padded_mask = tiled_mask.transpose((0, 2, 1, 3)).reshape(padded_image.shape[:-1])
        padded_mask = tiled_mask

        print('padded_mask', padded_mask.shape)

        print('pads:', pads)
        mask = padded_mask[
               pads[0][0]:padded_mask.shape[0] - pads[0][1],
               pads[1][0]:padded_mask.shape[1] - pads[1][1]]
        print('mask', mask.shape)

        # self._data_visualization_manager.visualize_data(
        #     FlatImage(mask, Palette.default_binary(rgb_color=[0, 255, 0])))


        # combined_image = tiled_image.transpose((0, 3, 1, 4, 2, 5)).reshape(padded_image.shape)
        # self._data_visualization_manager.visualize_data(FlatImage(combined_image))

        return mask


        tile = tiled_image[7]
        tile = tile.astype(np.float32)
        tile = (255 - tile) / 255

        tile_mask = self._segmenter.segment(tile)
        print('tile_mask', tile_mask.shape, tile_mask.dtype, tile_mask.min(), tile_mask.max())

        mask = np.zeros(shape=padded_image.shape[:-1], dtype=np.uint8)
        mask[:256, :256] = tile_mask > 0.5

        print('mask', mask.shape, mask.dtype, mask.min(), mask.max())

        self._data_visualization_manager.visualize_data(FlatImage(mask, Palette.default_binary(rgb_color=[0, 255, 0])))

        return


        img = np.swapaxes(tiles.reshape((8, 8, 192, 192, 3)), 1, 2)
        # # img = img.view((192*8, 192*8, 3))
        img = img.reshape((192 * 8, 192 * 8, 3))

        self._data_visualization_manager.visualize_data(FlatImage(img))

        img = img.astype(np.float32)
        img = 255 - img
        img /= 255

    @staticmethod
    def _tiled_image(image: np.ndarray, tile_size: int) -> np.ndarray:
        block_shape = (tile_size, tile_size, image.shape[-1])
        print('_tiled_image')
        print('padded image shape:', image.shape)
        print('block_shape:', block_shape)
        image = skimage.util.view_as_blocks(image, block_shape)
        print('view_as_blocks:', image.shape)
#        image = image.reshape(-1, *block_shape)
#        print('after reshape', image.shape)
        return image

    @staticmethod
    def _padded_image_to_tile(image: np.ndarray, tile_size: int, pad_value=255) -> tuple[np.ndarray, tuple]:
        h, w, c = image.shape

        pad_h = -h % tile_size
        pad_w = -w % tile_size
        pads = ((pad_h // 2, pad_h - pad_h // 2), (pad_w // 2, pad_w - pad_w // 2), (0, 0))
        image = np.pad(image, pads, constant_values=pad_value)
        return image, pads
