from __future__ import annotations

from pathlib import Path
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

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow


class BiocellPcGleasonSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_loading_manager_plugin':
            'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
        'data_visualization_manager_plugin':
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
    }

    _DNN_MODELS_DIR_NAME = 'dnn-models'
    _DATA_DIRS = (_DNN_MODELS_DIR_NAME,)

    def __init__(
            self,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
    ):
        super().__init__()

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager

        self._pc_gleason_segmenter: BiocellPcGleasonSegmenter | None = None

    @property
    def pc_gleason_segmenter(self) -> BiocellPcGleasonSegmenter | None:
        return self._pc_gleason_segmenter

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        model_params = DnnModelParams.from_config(
            self.config.value('gleason-segmenter-model'), self.data_path(self._DNN_MODELS_DIR_NAME))

        self._pc_gleason_segmenter = BiocellPcGleasonSegmenter(
            self._data_visualization_manager, model_params)

        # self._file_loading_manager.file_loaded.connect(self._pc_gleason_segmenter.segment)
        self._data_visualization_manager.data_visualized.connect(self._pc_gleason_segmenter.on_data_visualized)

    def _disable(self):
        self._pc_gleason_segmenter = None

        self._file_loading_manager = None
        self._data_visualization_manager = None

        raise NotImplementedError


class BiocellPcGleasonSegmenter(QObject):
    def __init__(self, data_visualization_manager: DataVisualizationManager, model_params: DnnModelParams):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._model_params = model_params

        self._segmenter = DnnSegmenter(self._model_params)

    def segment(self, data: Data):
        print('segment', type(data))

        if not isinstance(data, FlatImage):
            return

        image = data.pixels
        print('image:', image.shape, image.dtype, image.min(), image.max())

        mask = self._segment_image(image)

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
