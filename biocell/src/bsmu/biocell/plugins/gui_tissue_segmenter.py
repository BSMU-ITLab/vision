from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from timeit import default_timer as timer
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QMessageBox,
    QSlider, QVBoxLayout, QSpinBox, QWidget
)
from numpy.typing import DTypeLike

from bsmu.vision.core.config import Config
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.plugins.windows.main import AlgorithmsMenu, FileMenu
from bsmu.vision.plugins.writers.image.generic import GenericImageFileWriter
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.core.image.layered import LayeredImage
    from bsmu.vision.core.palette import Palette
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin
    from bsmu.vision.plugins.windows.main import MainWindow, MainWindowPlugin


@dataclass
class GradientCornerValues(Config):
    top_left: float = 1.0
    top_right: float = 1.0
    bottom_left: float = 1.0
    bottom_right: float = 1.0

    def __iter__(self):
        # Makes an instance of GradientCornerValues iterable, returning the values of its fields in order.
        return (getattr(self, f.name) for f in fields(self))

    def is_unit_gradient(self) -> bool:
        # Checks if all corner values are almost equal to 1.
        return all(math.isclose(value, 1.0) for value in self)

    def update_values(self, top_left: float, top_right: float, bottom_left: float, bottom_right: float):
        self.top_left = top_left
        self.top_right = top_right
        self.bottom_left = bottom_left
        self.bottom_right = bottom_right


@dataclass
class TissueSegmentationConfig(Config):
    blur_size: int = 3
    gradient_corner_values: GradientCornerValues = field(default_factory=GradientCornerValues)
    saturation_threshold: float = 0.075
    brightness_threshold: float = 0.03
    remove_small_object_size: int = 500
    fill_hole_size: int = 0


class GuiTissueSegmenterPlugin(Plugin):
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
        self._palette_pack_settings_plugin = palette_pack_settings_plugin

        self._gui_tissue_segmenter: GuiTissueSegmenter | None = None

    @property
    def gui_tissue_segmenter(self) -> GuiTissueSegmenter | None:
        return self._gui_tissue_segmenter

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window

        mdi = self._mdi_plugin.mdi
        main_palette = self._palette_pack_settings_plugin.settings.main_palette
        tissue_segmentation_config = TissueSegmentationConfig.from_dict(self.config_value('tissue_segmenter'))
        self._gui_tissue_segmenter = GuiTissueSegmenter(
            tissue_segmentation_config, mdi, main_palette, self._main_window)

        self._main_window.add_menu_action(
            FileMenu,
            self.tr('Save Tissue Mask and Config As...'),
            self._gui_tissue_segmenter.save_tissue_mask_and_config_as,
        )
        self._main_window.add_menu_action(
            AlgorithmsMenu,
            self.tr('Segment Tissue...'),
            self._gui_tissue_segmenter.segment_with_dialog,
        )

    def _disable(self):
        self._gui_tissue_segmenter = None

        self._main_window = None

        raise NotImplementedError


class GradientCornerEditor(QWidget):
    def __init__(self, config: GradientCornerValues, parent: QWidget = None):
        super().__init__(parent)

        self._config = config

        self._spin_boxes = []

        self._init_gui()

    @property
    def config(self) -> GradientCornerValues:
        return self._config

    def _init_gui(self):
        grid_layout = QGridLayout()

        config_corner_values_iter = iter(self._config)
        for row in range(2):
            for col in range(2):
                config_corner_value = next(config_corner_values_iter)

                spin_box = QDoubleSpinBox()
                spin_box.setRange(0.0, 1.0)
                spin_box.setValue(config_corner_value)
                spin_box.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)

                self._spin_boxes.append(spin_box)
                grid_layout.addWidget(spin_box, row, col)

        self.setLayout(grid_layout)

    def apply_changes(self):
        self._config.update_values(*(spin_box.value() for spin_box in self._spin_boxes))


class TissueSegmentationConfigDialog(QDialog):
    applied = Signal()

    def __init__(self, config: TissueSegmentationConfig, title: str, parent: QWidget = None):
        super().__init__(parent)

        self._config = config

        self.setWindowTitle(title)

        self._blur_size_spin_box: QSpinBox | None = None

        self._gradient_corner_editor: GradientCornerEditor | None = None

        self._saturation_threshold_slider: QSlider | None = None
        self._brightness_threshold_slider: QSlider | None = None

        self._saturation_spin_box: QDoubleSpinBox | None = None
        self._brightness_spin_box: QDoubleSpinBox | None = None

        self._remove_small_object_size_spin_box: QSpinBox | None = None
        self._fill_hole_size_spin_box: QSpinBox | None = None

        self._init_gui()

    @property
    def config(self) -> TissueSegmentationConfig:
        return self._config

    def _init_gui(self):
        # self._saturation_threshold_slider = QSlider(Qt.Horizontal)
        # self._saturation_threshold_slider.setValue(self._config.saturation_threshold)
        #
        # self._brightness_threshold_slider = QSlider(Qt.Horizontal)
        # self._brightness_threshold_slider.setValue(self._config.brightness_threshold)

        self._blur_size_spin_box = QSpinBox()
        self._blur_size_spin_box.setRange(0, 999)
        self._blur_size_spin_box.setValue(self._config.blur_size)

        self._gradient_corner_editor = GradientCornerEditor(self._config.gradient_corner_values)

        self._saturation_spin_box = QDoubleSpinBox()
        self._saturation_spin_box.setRange(0, 1)
        self._saturation_spin_box.setDecimals(3)
        self._saturation_spin_box.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
        self._saturation_spin_box.setValue(self._config.saturation_threshold)

        self._brightness_spin_box = QDoubleSpinBox()
        self._brightness_spin_box.setRange(0, 1)
        self._brightness_spin_box.setDecimals(3)
        self._brightness_spin_box.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
        self._brightness_spin_box.setValue(self._config.brightness_threshold)

        self._remove_small_object_size_spin_box = QSpinBox()
        self._remove_small_object_size_spin_box.setRange(0, 9999)
        self._remove_small_object_size_spin_box.setValue(self._config.remove_small_object_size)

        self._fill_hole_size_spin_box = QSpinBox()
        self._fill_hole_size_spin_box.setRange(0, 999)
        self._fill_hole_size_spin_box.setValue(self._config.fill_hole_size)

        form_layout = QFormLayout()
        form_layout.addRow(self.tr('Blur Size:'), self._blur_size_spin_box)
        form_layout.addRow(self.tr('Gradient Corner Values:'), self._gradient_corner_editor)
        form_layout.addRow(self.tr('Saturation Threshold:'), self._saturation_spin_box)
        form_layout.addRow(self.tr('Brightness Threshold:'), self._brightness_spin_box)
        form_layout.addRow(self.tr('Remove Small Object Size:'), self._remove_small_object_size_spin_box)
        form_layout.addRow(self.tr('Fill Hole Size:'), self._fill_hole_size_spin_box)

        button_box = QDialogButtonBox(QDialogButtonBox.Apply)
        apply_button = button_box.button(QDialogButtonBox.Apply)
        apply_button.pressed.connect(self._apply)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addStretch(1)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _apply(self):
        # self._config.saturation_threshold = self._saturation_threshold_slider.value()
        # self._config.brightness_threshold = self._brightness_threshold_slider.value()

        self._config.blur_size = self._blur_size_spin_box.value()
        self._gradient_corner_editor.apply_changes()
        self._config.saturation_threshold = self._saturation_spin_box.value()
        self._config.brightness_threshold = self._brightness_spin_box.value()
        self._config.remove_small_object_size = self._remove_small_object_size_spin_box.value()
        self._config.fill_hole_size = self._fill_hole_size_spin_box.value()

        self.applied.emit()


class GuiTissueSegmenter(QObject):
    def __init__(
            self,
            tissue_segmentation_config: TissueSegmentationConfig,
            mdi: Mdi,
            mask_palette: Palette,
            main_window: MainWindow = None,
    ):
        super().__init__()

        self._tissue_segmentation_config = tissue_segmentation_config
        self._main_window = main_window
        self._mdi = mdi
        self._mask_palette = mask_palette

        self._mask_layer_name = 'masks'

    def segment_with_dialog(self):
        tissue_segmentation_config_dialog = TissueSegmentationConfigDialog(
            self._tissue_segmentation_config, self.tr('Tissue Segmentation Settings'), self._main_window)
        tissue_segmentation_config_dialog.applied.connect(self.segment)
        tissue_segmentation_config_dialog.show()

    def segment(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        image_layer = layered_image.layers[0]
        image = image_layer.image
        tissue_segmenter = TissueSegmenter()
        mask = tissue_segmenter.segment(image.pixels, self._tissue_segmentation_config)

        layered_image.add_layer_or_modify_pixels(
            self._mask_layer_name,
            mask,
            FlatImage,
            self._mask_palette,
            Visibility(True, 0.5),
        )

    def save_tissue_mask_and_config_as(self):
        layered_image = self._active_layered_image()
        if layered_image is None:
            return

        save_path_str, selected_filter = QFileDialog.getSaveFileName(
            parent=self._main_window,
            caption=self.tr('Save Tissue Mask and Config'),
            dir=str(layered_image.layers[0].image_path.with_suffix('.png')),
            filter='PNG (*.png)',
        )
        if not save_path_str:
            return

        save_path = Path(save_path_str)
        try:
            GenericImageFileWriter().write_to_file(
                layered_image.layer_by_name(self._mask_layer_name).image, save_path)
            self._tissue_segmentation_config.save_to_yaml(save_path.with_suffix('.conf.yaml'))
        except Exception as e:
            QMessageBox.warning(
                self._main_window,
                'Save Error',
                f'Cannot save the mask.\n{e}')

    def _active_layered_image(self) -> LayeredImage | None:
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        return layered_image_viewer_sub_window and layered_image_viewer_sub_window.layered_image_viewer.data


class TissueSegmenter(QObject):
    def __init__(self):
        super().__init__()

    def segment(self, image: np.ndarray, config: TissueSegmentationConfig) -> np.ndarray:
        logging.info(f'Segment Tissue: {config}')

        # Convert image into float, else cv.cvtColor returns np.uint8 and we will lose conversion precision
        image = np.float32(image) / 255
        hsb_image = cv.cvtColor(image, cv.COLOR_RGB2HSV)

        if config.blur_size != 0:
            blur_kernel_size = (config.blur_size, config.blur_size)
            hsb_image = cv.GaussianBlur(hsb_image, blur_kernel_size, 0)

        saturation = hsb_image[..., 1]
        brightness = hsb_image[..., 2]

        if not config.gradient_corner_values.is_unit_gradient():
            gradient_application_start = timer()

            saturation *= self._generate_corner_gradient(saturation.shape, *config.gradient_corner_values)

            logging.debug(f'Gradient application time: {timer() - gradient_application_start}')

        _, saturation_thresholded = cv.threshold(saturation, config.saturation_threshold, 1, cv.THRESH_BINARY)
        _, brightness_thresholded = cv.threshold(brightness, config.brightness_threshold, 1, cv.THRESH_BINARY)

        mask = (saturation_thresholded > 0) & (brightness_thresholded > 0)

        if config.remove_small_object_size != 0:
            small_object_removing_start = timer()

            # small_object_removing_kernel_size = (config.remove_small_object_size, config.remove_small_object_size)
            # small_object_removing_kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, small_object_removing_kernel_size)
            # mask = self._mask_to_uint8(mask)
            # mask = cv.morphologyEx(mask, cv.MORPH_OPEN, small_object_removing_kernel)

            mask = self._mask_to_uint8(mask)
            self._remove_small_objects(mask, config.remove_small_object_size)

            logging.debug(f'Small object removing time: {timer() - small_object_removing_start}')

        if config.fill_hole_size != 0:
            holes_removing_start = timer()

            fill_hole_kernel_size = (config.fill_hole_size, config.fill_hole_size)
            fill_hole_kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, fill_hole_kernel_size)
            mask = self._mask_to_uint8(mask)
            mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, fill_hole_kernel)

            logging.debug(f'Holes removing time: {timer() - holes_removing_start}')

        return self._mask_to_uint8(mask)

    @staticmethod
    def _mask_to_uint8(mask: np.ndarray) -> np.ndarray:
        return mask if mask.dtype == np.uint8 else mask.astype(np.uint8)

    @staticmethod
    def _remove_small_objects(mask: np.ndarray, min_object_size: int):
        contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        # Filter out small objects
        for contour in contours:
            if cv.contourArea(contour) < min_object_size:
                # cv.drawContours(mask, [contour], contourIdx=-1, color=(0,), thickness=cv.FILLED)
                cv.fillPoly(mask, [contour], color=(0,))

    @staticmethod
    def _generate_corner_gradient(
            shape: tuple[int, int],
            top_left: float = 1.0,
            top_right: float = 1.0,
            bottom_left: float = 1.0,
            bottom_right: float = 1.0,
            dtype: DTypeLike = np.float32,
    ) -> np.ndarray:
        rows, cols = shape
        # Create a linear gradient for each corner horizontally
        top_gradient = np.linspace(top_left, top_right, cols, dtype=dtype)
        bottom_gradient = np.linspace(bottom_left, bottom_right, cols, dtype=dtype)

        # Interpolate the values for the rest of the array vertically
        gradient = np.linspace(top_gradient, bottom_gradient, rows, dtype=dtype)

        return gradient
