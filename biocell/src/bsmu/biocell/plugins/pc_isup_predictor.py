from __future__ import annotations

from timeit import default_timer as timer
from functools import partial
from typing import TYPE_CHECKING
from pathlib import Path
import numpy as np
import pandas as pd
import cv2 as cv
import skimage.io
from PySide6.QtCore import Qt, QObject
from collections.abc import Iterable
import skimage.util
from bsmu.vision.core.image import tile_splitter
from ctypes import CDLL

from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.models.table import TableColumn, TableItemDataRole
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from bsmu.vision.core.bbox import BBox
    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager


class BiocellPcIsupPredictorPlugin(Plugin):
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

        self._pc_isup_predictor: BiocellPcIsupPredictor | None = None

    @property
    def ms_predictor(self) -> BiocellPcIsupPredictor | None:
        return self._pc_isup_predictor

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        model_1_params = DnnModelParams.from_config(
            self.config.value('predictor_model_fold_1'), self.data_path(self._DNN_MODELS_DIR_NAME))
        model_2_params = model_1_params.copy_but_change_name(self.config.value('predictor_model_fold_4')['name'])
        model_3_params = model_1_params.copy_but_change_name(self.config.value('predictor_model_fold_5')['name'])

        self._pc_isup_predictor = BiocellPcIsupPredictor(
            self._data_visualization_manager, (model_1_params, model_2_params, model_3_params))

        # ms_prediction_score_item_delegate = MsPredictionScoreItemDelegate(self._table_visualizer)
        # self._table_visualizer.add_column(MsPredictionScoreTableColumn, ms_prediction_score_item_delegate)
        # self._table_visualizer.journal.record_added.connect(self._ms_predictor.add_observed_record)
        # self._table_visualizer.journal.record_removing.connect(self._ms_predictor.remove_observed_record)
        self._file_loading_manager.file_loaded.connect(self._pc_isup_predictor.predict)

    def _disable(self):
        self._pc_isup_predictor = None

        self._file_loading_manager = None

        raise NotImplementedError


class BiocellPcIsupPredictor(QObject):
    def __init__(self, data_visualization_manager: DataVisualizationManager, models_params: Iterable[DnnModelParams]):
        super().__init__()

        self._data_visualization_manager = data_visualization_manager
        self._models_params = models_params

        self._pc_predictors = tuple(DnnPredictor(model_params) for model_params in self._models_params)


        # self._predict_for_dir_images(
        #     Path(r'D:\Projects\pathological-cells\FromKaggle\train_images'),
        #     Path(r'D:\Projects\pathological-cells\FromKaggle\train.csv'),
        # )

        # self._import_openslide()

    def _import_openslide(self):
        print('file', __file__)
        p = Path(__file__).parents[4] / r'libss\openslide-win64-20171122\bin\libopenslide-0.dll'
        print('p', p)
        # my_cdll = CDLL(r'D:\Projects\vision\biocell\libss\openslide-win64-20171122\bin\libopenslide-0.dll')
        CDLL(str(p))

    def _test_openslide(self, slide):
        # import openslide

        # wsi_path = Path(r'D:\Projects\pathological-cells\FromKaggle\train_images\0a4b7a7499ed55c71033cefb0765e93d.tiff')
        # wsi_path = Path(r'D:\Projects\pathological-cells\data\2022_2483\2483-4a_22.svs')
        # slide = openslide.OpenSlide(wsi_path)
        print('\nslide', slide)
        print(f'dimensions: {slide.dimensions}\nlevel_count: {slide.level_count}\nlevel_dimensions: {slide.level_dimensions}')
        print(f'level_downsamples: {slide.level_downsamples}\nassociated_images: {slide.associated_images}')
        print(f'has properties: {hasattr(slide, "properties")}')
        print('properties:\n')
        # print(slide.properties)
        if 'tiff.ResolutionUnit' in slide.properties:
            print(f'Source resolution unit: {slide.properties["tiff.ResolutionUnit"]}')
        # Here we compute the "pixel spacing": the physical size of a pixel in the image.
        # OpenSlide gives the resolution in centimeters so we convert this to microns.
        if 'tiff.XResolution' in slide.properties:
            spacing_x = 1 / (float(slide.properties['tiff.XResolution']) / 10000)
            print(f'Microns per pixel / pixel spacing X: {spacing_x:.4f}')
        if 'tiff.YResolution' in slide.properties:
            spacing_y = 1 / (float(slide.properties['tiff.YResolution']) / 10000)
            print(f'Microns per pixel / pixel spacing Y: {spacing_y:.4f}')

        print('images')
        for im in slide.associated_images:
            print('-' * 20)
            print(im)

        downsample_factor = 7.53
        downsample_level = slide.get_best_level_for_downsample(downsample_factor)
        print('downsample_level', downsample_level)
        needed_level_dimensions = slide.level_dimensions[downsample_level]
        if needed_level_dimensions[0] * needed_level_dimensions[1] > 30000 * 30000:
            print('TOO BIG IMAGE!!!')
            return
        region = slide.read_region((0, 0), downsample_level, needed_level_dimensions)
        print('type', type(region))
        region = np.array(region)
        print('region', region.shape, region.min(), region.max(), region.dtype)

        region_downsample_factor = slide.level_downsamples[downsample_level]
        downsample_factor /= region_downsample_factor

        region = cv.resize(region, (int(region.shape[1] // downsample_factor), int(region.shape[0] // downsample_factor)), interpolation=cv.INTER_AREA)
        print('after RESIZE region', region.shape, region.min(), region.max(), region.dtype)

        self._data_visualization_manager.visualize_data(FlatImage(region))

        # Remove alpha-channel
        if region.shape[2] == 4:
            region = region[..., :3]
        self._predict_for_image(region)

        return

    def _test_slideio(self, data: Data):
        import slideio

        slide = slideio.open_slide(str(data.path), "SVS")
        print('sss', slide)
        raw_string = slide.raw_metadata
        print('raw_metadata:', raw_string)
        raw_string.split("|")
        print('meta', raw_string)

        scene = slide.get_scene(0)
        print('info:', scene.name, scene.rect, scene.num_channels, scene.resolution, scene.magnification)
        print('aux_images', scene.num_aux_images)

        full_resolution_width = scene.rect[2]
        print('full_resolution_width:', full_resolution_width)
        start = timer()
        # img = scene.read_block(size=(round(full_resolution_width / 7.5328), 0))
        region = scene.read_block(size=(round(full_resolution_width / 7.53), 0))
        end = timer()
        print('Time to read rescaled block:', end - start)
        print('img', region.shape, region.min(), region.max(), region.dtype)

        self._data_visualization_manager.visualize_data(FlatImage(region))

        # Remove alpha-channel
        if region.shape[2] == 4:
            region = region[..., :3]
        self._predict_for_image(region)

    def predict(self, data: Data):
        # self._test_openslide(data.slide)
        # self._test_slideio(data)
        # return


        print('predict', type(data))

        if not isinstance(data, FlatImage):
            return

        img = data.pixels
        self._predict_for_image(img)

    def _predict_for_image(self, img: np.ndarray):
        # img = cv.resize(img, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv.INTER_AREA)

        tiles, idxs = self._tiled(img, 192, 64)
        # img = tile_splitter.merge_tiles_into_image(tiles, (64, 64))

        img = np.swapaxes(tiles.reshape((8, 8, 192, 192, 3)), 1, 2)
        # # img = img.view((192*8, 192*8, 3))
        img = img.reshape((192 * 8, 192 * 8, 3))

        self._data_visualization_manager.visualize_data(FlatImage(img))

        img = img.astype(np.float32)
        img = 255 - img
        img /= 255

#        print('Before prediction:', img.dtype, img.shape)

        ensemble_isup = 0
        ensemble_glisson = 0

        for i, pc_predictor in enumerate(self._pc_predictors):
            # pc_predictor.predict_async(img, partial(self._on_pc_predicted, pc_predictor))

            pc_prediction = pc_predictor.predict(img)
            pc_prediction = self.sigmoid_array(pc_prediction)
            isup = pc_prediction[:5].sum()
            glisson = pc_prediction[5:].sum()
            print(f'  #{i}')
            # print('AAAAAAAAAAAAA', type(isup))
            # print(isup.round(5))
            # print(round(isup, 5))
            # print(np.around(isup, 5))
            # isup_rounded = isup.round(3)
            # glisson_rounded = glisson.round(3)
            print(f'  isup: {round(isup)}\t\t{isup:.3f}')
            # print(isup.round(3))
            print(f'  glis: {round(glisson)}\t\t{glisson:.3f}')
            # print(glisson.round(3))
            ensemble_isup += isup
            ensemble_glisson += glisson
        isup = ensemble_isup / len(self._pc_predictors)
        glisson = ensemble_glisson / len(self._pc_predictors)
        print(f'ensemble isup: {round(isup)}\t\t{round(isup, 3)}')
        print(f'ensemble glis: {round(glisson)}\t\t{round(glisson, 3)}')

    def _on_pc_predicted(self, pc_predictor: DnnPredictor, pc_prediction: np.ndarray):
        print(f'\t\t=== {pc_predictor.model_params.path.name} ===')
        # print('pc_prediction', pc_prediction)
        pc_prediction = self.sigmoid_array(pc_prediction)
        # print('pc_prediction', pc_prediction)

        isup_sum = round(pc_prediction[:5].sum())
        glisson_sum = round(pc_prediction[5:].sum())

        isup = np.round(pc_prediction[:5])
        glisson = np.round(pc_prediction[5:])

        print(f'isup {isup}\t\t{isup_sum}')
        print(f'glisson {glisson}\t\t{glisson_sum}')

        # pc_prediction = pc_prediction > 0

    def sigmoid_array(self, x):
        return 1 / (1 + np.exp(-x))

    def as_tiles(self, image: np.ndarray, tile_size: int):
        new_shape = (tile_size, tile_size, image.shape[-1])
#        print('as_tiles0', image.shape)
        image = skimage.util.view_as_blocks(image, new_shape)
#        print('as_tiles1', image.shape)
        image = image.reshape(-1, *new_shape)
#        print('as_tiles2', image.shape)
        return image #image.reshape(-1, *new_shape)

    def _tiled(self, image: np.ndarray, tile_size: int, n_tiles: int, pad_value=255):
        # print('IMAGE type:', image.dtype, image.min(), image.max())

        h, w, c = image.shape

        pad_h = -h % tile_size
        pad_w = -w % tile_size

        pad = ((pad_h // 2, pad_h - pad_h // 2), (pad_w // 2, pad_w - pad_w // 2), (0, 0))

        image = np.pad(image, pad, constant_values=pad_value)
        image = self.as_tiles(image, tile_size)
        idxs = np.argsort(image.reshape(image.shape[0], -1).sum(-1))[:n_tiles]
#        print('Bef', image.shape,   idxs.shape)
        image = image[idxs]
#        print('aft', image.shape)

        if len(image) < n_tiles:
            pad = ((0, n_tiles - len(image)), (0, 0), (0, 0), (0, 0))
            image = np.pad(image, pad, constant_values=pad_value)

#        print('aft', image.shape)
        return image, idxs

    def _predict_for_dir_images(self, image_dir: Path, csv_path: Path):
        data_frame = pd.read_csv(str(csv_path), index_col=0)
        for image_path in image_dir.iterdir():
            if image_path.is_file():
                print('=' * 80)
                print('=' * 80)
                print(f'\t\t\t\t===== {image_path.name} =====')
                record = data_frame.loc[image_path.stem]
                print(f'\t\t\t{record.data_provider}  isup: {record.isup_grade}   gleason: {record.gleason_score}')

                multi_image_level = 1
                pixels = skimage.io.MultiImage(str(image_path), key=multi_image_level)[0]
                self._predict_for_image(pixels)
