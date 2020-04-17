from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject, Qt

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import MenuType
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision_core.image.base import VolumeImage
from bsmu.vision_core.palette import Palette

if TYPE_CHECKING:
    from bsmu.vision.app import App
    from bsmu.vision.plugins.doc_interfaces.mdi import Mdi


class ColorContrastPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        mdi = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin').mdi

        self.color_contrast = ColorContrast(mdi)

    def _enable(self):
        menu_action = self.main_window.add_menu_action(
            MenuType.ALGORITHMS, 'Color Contrast', self.color_contrast.create_colored_image,
            Qt.CTRL + Qt.Key_H)

    def _disable(self):
        raise NotImplementedError


class ColorContrast(QObject):
    def __init__(self, mdi: Mdi):
        super().__init__()

        self.mdi = mdi

    def create_colored_image_1(self):
        active_sub_window = self.mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredImageViewerSubWindow):
            return

        layered_image = active_sub_window.viewer.data
        layered_image.print_layers()
        image = layered_image.layer_by_name('series').image
        print('stat', image.array.shape, image.array.min(), image.array.max(), image.array.dtype)
        print(np.unique(image.array))

        norm = (image.array / image.array.max() * 255).astype(np.uint8)
        print('norm stat', norm.shape, norm.min(), norm.max(), norm.dtype)

        import colorsys
        palette_array = np.zeros((256, 4), dtype=np.uint8)
        for i in range(256):
            print('hsv', i, 60, 80)
            hsv_decimal = (i / 360, 60 / 100, 80 / 100)
            rgb_decimal = colorsys.hsv_to_rgb(*hsv_decimal)
            rgb = tuple(round(i * 255) for i in rgb_decimal)
            palette_array[i] = [*rgb, 255]
            print('res conv', palette_array[i])

        palette = Palette(palette_array)
        indexed_image = VolumeImage(norm, palette, spatial=image.spatial)

        layered_image.add_layer_from_image(indexed_image, 'colored')

        # print('rgb stat', rgb.shape, rgb.min(), rgb.max(), rgb.dtype)

    def create_colored_image_2(self):
        active_sub_window = self.mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredImageViewerSubWindow):
            return

        layered_image = active_sub_window.viewer.data
        layered_image.print_layers()
        image = layered_image.layer_by_name('series').image
        print('stat', image.array.shape, image.array.min(), image.array.max(), image.array.dtype)
        print(np.unique(image.array))

        norm = (image.array / image.array.max() * 511).astype(np.int)
        print('norm stat', norm.shape, norm.min(), norm.max(), norm.dtype)

        import colorsys
        palette_array = np.zeros((512, 4), dtype=np.uint8)
        h = 0
        b = 80
        i = 0
        while i < 512:
            for s in range(60, 100):
                print('i', i, ' hsv', h, s, b)
                hsv_decimal = (h / 360, s / 100, b / 100)
                rgb_decimal = colorsys.hsv_to_rgb(*hsv_decimal)
                rgb = tuple(round(c * 255) for c in rgb_decimal)
                palette_array[i] = [*rgb, 255]
                print('res conv', palette_array[i])
                i += 1
                if i >= 512:
                    break
            h += 24

        palette = Palette(palette_array)
        indexed_image = VolumeImage(norm, palette, spatial=image.spatial)

        layered_image.add_layer_from_image(indexed_image, 'colored')

        # print('rgb stat', rgb.shape, rgb.min(), rgb.max(), rgb.dtype)

    def create_colored_image(self):
        active_sub_window = self.mdi.activeSubWindow()
        if not isinstance(active_sub_window, LayeredImageViewerSubWindow):
            return

        layered_image = active_sub_window.viewer.data
        layered_image.print_layers()
        image = layered_image.layer_by_name('series').image
        print('stat', image.array.shape, image.array.min(), image.array.max(), image.array.dtype)
        print(np.unique(image.array))

        discrete_color_len = 2000
        norm = (image.array / image.array.max() * (discrete_color_len - 1)).astype(np.int)
        print('norm stat', norm.shape, norm.min(), norm.max(), norm.dtype)

        import colorsys
        palette_array = np.zeros((discrete_color_len, 4), dtype=np.uint8)
        h_min = 0
        h_max = 360
        s_min = 70
        s_max = 100
        b = 80

        h_range = h_max - h_min
        s_range = s_max - s_min
        color_range = h_range * s_range

        color_delta = color_range / discrete_color_len
        for i in range(discrete_color_len):
            v = color_delta * i
            h = h_min + (v // s_range)
            s = s_min + (v % s_range)

            # h = h_max - h
            print('i', i, ' hsv', h, s, b)
            hsv_decimal = (h / 360, s / 100, b / 100)
            rgb_decimal = colorsys.hsv_to_rgb(*hsv_decimal)
            rgb = tuple(round(c * 255) for c in rgb_decimal)
            # palette_array[discrete_color_len - i - 1] = [*rgb, 255]
            palette_array[i] = [*rgb, 255]
            print('res conv', palette_array[i])

        palette = Palette(palette_array)
        indexed_image = VolumeImage(norm, palette, spatial=image.spatial)

        layered_image.add_layer_from_image(indexed_image, 'colored')

        # print('rgb stat', rgb.shape, rgb.min(), rgb.max(), rgb.dtype)
