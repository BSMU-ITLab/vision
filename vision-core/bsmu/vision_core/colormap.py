from __future__ import annotations

from PySiside2.QtCore import QObject, Signal

from core import settings

import numpy as np


class Colormap(QObject):
    changed = Signal()  #% rename to lut_changed
    active_color_class_changed = Signal(int)

    def __init__(self):
        super().__init__()

        self.lut = np.zeros((12, 4), np.uint8)
        self.premultiplied_lut = np.zeros_like(self.lut)

        self.set_class_color_array(settings.NO_MASK_CLASS, settings.NO_MASK_COLOR)
        self.set_class_color_array(settings.MASK_CLASS, settings.MASK_COLOR)
        self.set_class_color_array(settings.TOOL_BACKGROUND_CLASS, settings.TOOL_BACKGROUND)
        self.set_class_color_array(settings.TOOL_FOREGROUND_CLASS, settings.TOOL_FOREGROUND)
        self.set_class_color_array(settings.TOOL_ERASER_CLASS, settings.TOOL_ERASER)
        self.set_class_color_array(settings.TOOL_NO_COLOR_CLASS, settings.TOOL_NO_COLOR)

        self.set_class_color_array(6, [255, 90, 90, 80])
        self.set_class_color_array(7, [90, 90, 255, 80])
        self.set_class_color_array(8, [120, 180, 255, 80])
        self.set_class_color_array(9, [255, 120, 180, 80])
        self.set_class_color_array(10, [120, 255, 180, 80])
        self.set_class_color_array(settings.TOOL_BACKGROUND_2_CLASS, settings.TOOL_BACKGROUND_2)

        self.active_color_class = settings.MASK_CLASS

        '''
        self.lut = np.array([settings.NO_MASK_COLOR,
                             settings.MASK_COLOR,
                             settings.TOOL_BACKGROUND,
                             settings.TOOL_FOREGROUND,
                             settings.TOOL_ERASER,
                             settings.TOOL_NO_COLOR])
        '''

    def set_active_color_class(self, class_number: int):
        if self.active_color_class != class_number:
            self.active_color_class = class_number
            self.active_color_class_changed.emit(class_number)

    def set_class_color_array(self, class_number: int, color_array):
        if (self.lut[class_number] != color_array).any():
            self.lut[class_number] = color_array

            premultiplied_color_array = np.copy(color_array)
            premultiplied_color_array[:3] = np.rint(premultiplied_color_array[:3] / 255 * premultiplied_color_array[3])
            self.premultiplied_lut[class_number] = premultiplied_color_array

            self.changed.emit()

    def set_class_color(self, class_number: int, color: QColor):
        color_array = np.array([color.red(), color.green(), color.blue(), color.alpha()], np.uint8)
        self.set_class_color_array(class_number, color_array)

    def colored_image(self, image):
        return self.lut[image]

    def colored_premultiplied_image(self, image):
        return self.premultiplied_lut[image]
