from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import skimage.color
from PySide6.QtCore import Qt, QObject
from PySide6.QtWidgets import QMessageBox

from bsmu.vision.core.converters.image import normalized_uint8
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


TISSUE_MASK_LAYER_NAME = 'tissue-mask'
BLUE_MASK_LAYER_NAME = 'blue-mask'


class BiocellKidneyTissueSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._kidney_tissue_segmenter: BiocellKidneyTissueSegmenter | None = None

    def _enable(self):
        self._kidney_tissue_segmenter = BiocellKidneyTissueSegmenter()

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Tissue', self._segment_tissue, Qt.Key_9)
        self._main_window.add_menu_action(AlgorithmsMenu, 'Analyze Blue Ratio', self._analyze_blue_ratio, Qt.Key_0)

    def _disable(self):
        self._mdi_viewer_tool = None
        self._tool_action = None

        raise NotImplementedError

    def _segment_tissue(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        self._kidney_tissue_segmenter.segment_tissue(layered_image_viewer)

    def _analyze_blue_ratio(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        self._kidney_tissue_segmenter.analyze_blue_ratio(layered_image_viewer)


def show_rgb(rgb: np.ndarray, title: str = ''):
    if rgb.dtype == np.float64:
        rgb = rgb.astype(np.float32, copy=False)
    cv.imshow(title, cv.cvtColor(rgb, cv.COLOR_RGB2BGR))


class BiocellKidneyTissueSegmenter(QObject):
    def __init__(self):
        super().__init__()

    def segment_tissue(self, layered_image_viewer: LayeredImageViewer):
        print('segment_tissue', type(layered_image_viewer))

        image = layered_image_viewer.active_layer.image
        # show_rgb(image.pixels, 'Image')

        # RGB to Haematoxylin-Eosin-DAB (HED) color space conversion
        # hed = skimage.color.rgb2hed(image.pixels)

        # hed_from_rgb: Hematoxylin + Eosin + DAB
        # hdx_from_rgb: Hematoxylin + DAB
        # fgx_from_rgb: Feulgen + Light Green
        # bex_from_rgb: Giemsa stain : Methyl Blue + Eosin
        # rbd_from_rgb: FastRed + FastBlue + DAB
        # gdx_from_rgb: Methyl Green + DAB
        # hax_from_rgb: Hematoxylin + AEC
        # bro_from_rgb: Blue matrix Anilline Blue + Red matrix Azocarmine + Orange matrix Orange-G
        # bpx_from_rgb: Methyl Blue + Ponceau Fuchsin
        # ahx_from_rgb: Alcian Blue + Hematoxylin
        # hpx_from_rgb: Hematoxylin + PAS
        stains = skimage.color.separate_stains(image.pixels, skimage.color.hed_from_rgb)
        stain_0 = stains[..., 0]
        print(f'stain_0:  shape={stain_0.shape}  dtype={stain_0.dtype}  min={stain_0.min()}  max={stain_0.max()}')
        # show_rgb(stain_0, '0')
        #
        stain_1 = stains[..., 1]
        print(f'stain_1:  shape={stain_1.shape}  dtype={stain_1.dtype}  min={stain_1.min()}  max={stain_1.max()}')
        # show_rgb(stain_1, '1')
        #
        stain_2 = stains[..., 2]
        print(f'stain_2:  shape={stain_2.shape}  dtype={stain_2.dtype}  min={stain_2.min()}  max={stain_2.max()}')
        # show_rgb(stain_2, '2')

        stain_0_normalized_uint8 = normalized_uint8(stain_0)
        print(f'stain_0 normalized:  shape={stain_0_normalized_uint8.shape}  dtype={stain_0_normalized_uint8.dtype}  '
              f'min={stain_0_normalized_uint8.min()}  max={stain_0_normalized_uint8.max()}  '
              f'mean={np.mean(stain_0_normalized_uint8)}')
        stain_1_normalized_uint8 = normalized_uint8(stain_1)
        stain_2_normalized_uint8 = normalized_uint8(stain_2)

        tissue_mask = np.zeros_like(stain_0_normalized_uint8)
        tissue_mask[np.where((stain_0_normalized_uint8 > 1) | (stain_2_normalized_uint8 > 7))] = 1
        tissue_palette = Palette.default_binary(rgb_color=[131, 151, 98])
        layered_image_viewer.data.add_layer_or_modify_pixels(
            TISSUE_MASK_LAYER_NAME, tissue_mask, FlatImage, tissue_palette)

        blue_mask = np.zeros_like(stain_0_normalized_uint8)
        blue_mask[stain_0_normalized_uint8 > 14] = 1
        self._analyze_blue_ratio(layered_image_viewer, tissue_mask, blue_mask)

    def analyze_blue_ratio(self, layered_image_viewer: LayeredImageViewer):
        print('analyze_blue_ratio', type(layered_image_viewer))

        tissue_mask_layer = layered_image_viewer.layer_by_name(TISSUE_MASK_LAYER_NAME)
        blue_mask_layer = layered_image_viewer.layer_by_name(BLUE_MASK_LAYER_NAME)
        if not (tissue_mask_layer and blue_mask_layer):
            QMessageBox.information(layered_image_viewer, 'No Masks', 'Run "Segment Tissue" action first.')
            return
        self._analyze_blue_ratio(layered_image_viewer, tissue_mask_layer.image_pixels, blue_mask_layer.image_pixels)

    def _analyze_blue_ratio(
            self, layered_image_viewer: LayeredImageViewer, tissue_mask: np.ndarray, blue_mask: np.ndarray):
        # Set the |blue_mask| to zero where tissue mask is zeros (tissue mask can be erased by brash)
        blue_mask[tissue_mask == 0] = 0
        blue_palette = Palette.default_binary(rgb_color=[255, 179, 19])
        layered_image_viewer.data.add_layer_or_modify_pixels(
            BLUE_MASK_LAYER_NAME, blue_mask, FlatImage, blue_palette)

        print('\n=== Initial Result ===')
        blue_mask[tissue_mask == 0] = 0
        blue_to_tissue_ratio = self._pixel_count_ratio(blue_mask, tissue_mask)

        print('\n=== After Erode ===')
        erode_kernel = np.ones((3, 3), np.uint8)
        blue_mask = cv.erode(blue_mask, kernel=erode_kernel, iterations=1)
        eroded_blue_to_tissue_ratio = self._pixel_count_ratio(blue_mask, tissue_mask)

        blue_eroded_palette = Palette.default_binary(rgb_color=[255, 110, 19])
        layered_image_viewer.data.add_layer_or_modify_pixels(
            'blue-eroded_mask', blue_mask, FlatImage, blue_eroded_palette)

        ratio_message = f'Blue: {self._float_to_persent_str(blue_to_tissue_ratio)}' \
                        f'\nEroded Blue: {self._float_to_persent_str(eroded_blue_to_tissue_ratio)}'
        QMessageBox.information(layered_image_viewer, 'Blue Ratio', ratio_message)

    def _pixel_count_ratio(self, a: np.ndarray, b: np.ndarray) -> float:
        a_pixel_count = cv.countNonZero(a)
        b_pixel_count = cv.countNonZero(b)
        a_to_b_ratio = a_pixel_count / b_pixel_count
        print(f'a_pixel_count: {a_pixel_count}  b_pixel_count: {b_pixel_count}  ratio: {a_to_b_ratio}')
        return a_to_b_ratio

    def _float_to_persent_str(self, value: float) -> str:
        return f'{value * 100:.2f}%'
