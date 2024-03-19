from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import skimage.color
from PySide6.QtCore import Qt, QObject
from PySide6.QtWidgets import QMessageBox
from skimage import morphology

from bsmu.vision.core.converters.image import normalized_uint8
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


MASKS_LAYER_NAME = 'masks'
SEGMENT_TISSUE_ACTION_NAME = 'Segment Tissue - Stain Separation'


class BiocellKidneyTissueSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._palette_pack_settings_plugin = palette_pack_settings_plugin

        self._kidney_tissue_segmenter: BiocellKidneyTissueSegmenter | None = None

    def _enable(self):
        main_palette = self._palette_pack_settings_plugin.settings.main_palette
        self._kidney_tissue_segmenter = BiocellKidneyTissueSegmenter(main_palette)

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._mdi = self._mdi_plugin.mdi

        self._main_window.add_menu_action(AlgorithmsMenu, SEGMENT_TISSUE_ACTION_NAME, self._segment_tissue, Qt.Key_9)
        # self._main_window.add_menu_action(AlgorithmsMenu, 'Segment Tissue - Saturation Threshold', self._segment_tissue_using_saturation_threshold, Qt.Key_7)
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

    def _segment_tissue_using_saturation_threshold(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        self._kidney_tissue_segmenter.segment_tissue_using_saturation_threshold(layered_image_viewer)

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
    def __init__(self, mask_palette: Palette):
        super().__init__()

        self._mask_palette = mask_palette
        self._mask_background_class = mask_palette.row_index_by_name('background')
        self._mask_foreground_class = mask_palette.row_index_by_name('foreground')
        self._mask_blue_class = mask_palette.row_index_by_name('blue')
        self._mask_eroded_blue_class = mask_palette.row_index_by_name('eroded_blue')

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

        mask = np.zeros_like(stain_0_normalized_uint8)
        mask[(stain_0_normalized_uint8 > 1) | (stain_2_normalized_uint8 > 7)] = self._mask_foreground_class

        is_blue_mask = stain_0_normalized_uint8 > 14
        mask[is_blue_mask] = self._mask_blue_class

        erode_kernel = np.ones((3, 3), np.uint8)
        blue_eroded_mask = cv.erode(is_blue_mask.astype(np.uint8), kernel=erode_kernel, iterations=1)
        mask[blue_eroded_mask.astype(bool)] = self._mask_eroded_blue_class

        layered_image_viewer.data.add_layer_or_modify_pixels(
            MASKS_LAYER_NAME, mask, FlatImage, self._mask_palette)

        self._analyze_blue_ratio(layered_image_viewer, mask)

    def analyze_blue_ratio(self, layered_image_viewer: LayeredImageViewer):
        print('analyze_blue_ratio', type(layered_image_viewer))

        mask_layer = layered_image_viewer.layer_by_name(MASKS_LAYER_NAME)
        if not mask_layer:
            QMessageBox.information(
                layered_image_viewer, 'No Masks', f'Run <b>{SEGMENT_TISSUE_ACTION_NAME}</b> action first.')
            return
        self._analyze_blue_ratio(layered_image_viewer, mask_layer.image_pixels)

    def _analyze_blue_ratio(self, layered_image_viewer: LayeredImageViewer, mask: np.ndarray):
        print('\n=== Initial Result ===')
        # Do not use: tissue_mask = mask != self._mask_background_class, because we can have some non tissue classes
        is_tissue_mask = \
            (mask == self._mask_foreground_class) \
            | (mask == self._mask_blue_class) \
            | (mask == self._mask_eroded_blue_class)

        is_blue_mask = (mask == self._mask_blue_class) | (mask == self._mask_eroded_blue_class)
        blue_to_tissue_ratio = self._pixel_count_ratio(is_blue_mask, is_tissue_mask)

        print('\n=== After Erode ===')
        eroded_blue_to_tissue_ratio = self._pixel_count_ratio(mask == self._mask_eroded_blue_class, is_tissue_mask)

        ratio_message = f'Blue: {self._float_to_persent_str(blue_to_tissue_ratio)}' \
                        f'\nEroded Blue: {self._float_to_persent_str(eroded_blue_to_tissue_ratio)}'
        QMessageBox.information(layered_image_viewer, 'Blue Ratio', ratio_message)

    def segment_tissue_using_saturation_threshold(self, layered_image_viewer: LayeredImageViewer):
        print('segment_tissue_using_saturation_threshold', type(layered_image_viewer))

        image = layered_image_viewer.active_layer.image

        # tissue_mask = _get_tissue(image.array, thresh=0, gauss_kernel=(5, 5), cv2flags=cv.THRESH_OTSU)
        # tissue_mask = _get_tissue(image.pixels, thresh=25, gauss_kernel=(5, 5))
        tissue_mask = _get_tissue(image.pixels, thresh=1, gauss_kernel=(41, 41), sensivity_holes=300, sensivity_objects=300)
        tissue_mask = tissue_mask.astype(np.uint8)
        print(f'tissue_mask: {tissue_mask.min()} {tissue_mask.max()} {np.unique(tissue_mask)}  {tissue_mask.dtype}')

        # skimage.io.imsave(str(r'D:/Temp/MMM.png'), tissue_mask, check_contrast=False)

        tissue_palette = Palette.default_binary(rgb_color=[131, 151, 98])
        layered_image_viewer.data.add_layer_or_modify_pixels(
            MASKS_LAYER_NAME, tissue_mask, FlatImage, tissue_palette)

    def _pixel_count_ratio(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.dtype == bool:
            a = a.astype(np.uint8)
        if b.dtype == bool:
            b = b.astype(np.uint8)
        a_pixel_count = cv.countNonZero(a)
        b_pixel_count = cv.countNonZero(b)
        a_to_b_ratio = a_pixel_count / b_pixel_count if b_pixel_count != 0 else 0
        print(f'a_pixel_count: {a_pixel_count}  b_pixel_count: {b_pixel_count}  ratio: {a_to_b_ratio}')
        return a_to_b_ratio

    def _float_to_persent_str(self, value: float) -> str:
        return f'{value * 100:.2f}%'


def _apply_threshold(image, thresh=0, gauss_kernel=(5, 5), cv2flags=cv.THRESH_OTSU):
    if gauss_kernel is not None:
        image = cv.GaussianBlur(image, gauss_kernel, 0)

    _, threshold_image = cv.threshold(
        image, thresh, 255, cv.THRESH_BINARY + cv2flags
    )

    return threshold_image


def _get_tissue(rgb_image, thresh=7, sensivity_holes=3000, sensivity_objects=3000, gauss_kernel=None, cv2flags=0):
    hsv_image = cv.cvtColor(rgb_image, cv.COLOR_RGB2HSV)

    saturation = hsv_image[..., 1]

    kernel = np.full((5, 5), -1.)
    kernel[2, 2] = 25
    kernel /= 12.5
    saturation = cv.filter2D(saturation, -1, kernel)

    value = hsv_image[..., 2]
    saturation[value == 255] = 0

    mask = _apply_threshold(saturation, thresh, gauss_kernel, cv2flags)

    mask = mask != 0

    if sensivity_holes is not None:
        mask = morphology.remove_small_holes(mask, area_threshold=sensivity_holes)
    if sensivity_objects is not None:
        mask = morphology.remove_small_objects(mask, min_size=sensivity_objects)

    return mask
