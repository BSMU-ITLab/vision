from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import skimage.color
from PySide6.QtCore import Qt

from bsmu.vision.plugins.tools.viewer.image.wsi_smart_brush import WsiSmartBrushImageViewerToolPlugin, \
    WsiSmartBrushImageViewerTool, WsiSmartBrushImageViewerToolSettings, WsiSmartBrushImageViewerToolSettingsWidget

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools.viewer.base import ViewerTool, ViewerToolSettings, ViewerToolSettingsWidget
    from bsmu.vision.plugins.undo import UndoPlugin, UndoManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewer


def normalize_between_0_1(array: np.ndarray) -> np.ndarray:
    array_min = array.min()
    return (array - array_min) / ((array.max() - array_min) or 1)


def show_rgb(rgb: np.ndarray, title: str = ''):
    if rgb.dtype == np.float64:
        rgb = rgb.astype(np.float32, copy=False)
    cv.imshow(title, cv.cvtColor(rgb, cv.COLOR_RGB2BGR))


class HedSmartBrushImageViewerToolSettings(WsiSmartBrushImageViewerToolSettings):
    pass


class HedSmartBrushImageViewerToolSettingsWidget(WsiSmartBrushImageViewerToolSettingsWidget):
    pass


class HedSmartBrushImageViewerTool(WsiSmartBrushImageViewerTool):
    def __init__(
            self,
            viewer: LayeredImageViewer,
            undo_manager: UndoManager,
            settings: HedSmartBrushImageViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

    def _preprocess_downscaled_image_in_brush_bbox(self, image: np.ndarray):
        # print('before preprocess: ', image.dtype, image.shape, image.min(), image.max())

        # RGB to Haematoxylin-Eosin-DAB (HED) color space conversion
        hed = skimage.color.rgb2hed(image)
        h = hed[..., 0]

        # h = image[..., 0]

        # show_rgb(h, 'H')
        # return h



        # h = normalize_between_0_1(h)
        #
        # h[h > 0.3] = 0
        # h = normalize_between_0_1(h)



        # h[h > 0.25] = 0.25
###        h = normalize_between_0_1(h)

        # print('YYYYYY norm', h.shape, h.dtype, h.min(), h.max())

        # return h

        blur_size = round(max(image.shape[:2]) / 10)
        if blur_size % 2 == 0:
            blur_size += 1
        # print('blur_size:', blur_size)
        blured = cv.GaussianBlur((h * 255).astype(np.uint8), (blur_size, blur_size), 0)
        # blured = cv.GaussianBlur((h * 255).astype(np.uint8), (3, 3), 0)
        # blured = cv.GaussianBlur((h * 255).astype(np.uint8), (19, 19), 0)

        # show_rgb(normalize_between_0_1(blured), 'Blured Normalized')

        return blured


        threshold_value, thresholded_image = cv.threshold(blured, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
        return thresholded_image

        print(' after preprocess: ', image.dtype, image.shape, image.min(), image.max())
        return image


class HedSmartBrushImageViewerToolPlugin(WsiSmartBrushImageViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: Type[ViewerTool] = HedSmartBrushImageViewerTool,
            tool_settings_cls: Type[ViewerToolSettings] = HedSmartBrushImageViewerToolSettings,
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget] = HedSmartBrushImageViewerToolSettingsWidget,
            action_name: str = 'Smart Brush (HED)',
            action_shortcut: Qt.Key = Qt.Key_2,
    ):
        super().__init__(
            main_window_plugin,
            mdi_plugin,
            undo_plugin,
            palette_pack_settings_plugin,
            tool_cls,
            tool_settings_cls,
            tool_settings_widget_cls,
            action_name,
            action_shortcut,
        )
