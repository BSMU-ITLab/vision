from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFormLayout, QDoubleSpinBox

from bsmu.vision.plugins.settings import SettingsPlugin
from bsmu.vision.plugins.windows.main import SettingsMenu
from bsmu.vision.widgets.settings import SettingsWidget
from bsmu.vision.widgets.viewers.graphics import ImageViewerSettings

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.plugins.windows.main import MainWindowPlugin


class ImageViewerSettingsWidget(SettingsWidget):
    def __init__(self, settings: ImageViewerSettings, parent: QWidget = None):
        super().__init__(settings, parent)

        layout = QFormLayout()

        self._zoom_factor_spin_box = QDoubleSpinBox()
        self._zoom_factor_spin_box.setValue(self.settings.graphics_view_settings.zoom_settings.zoom_factor)
        self._zoom_factor_spin_box.valueChanged.connect(self._on_zoom_factor_spin_box_value_changed)
        self.settings.graphics_view_settings.zoom_settings.zoom_factor_changed.connect(
            self._on_settings_zoom_factor_changed)
        layout.addRow('&Zoom Factor:', self._zoom_factor_spin_box)

        self.setLayout(layout)

    def _on_zoom_factor_spin_box_value_changed(self, value: float):
        self.settings.graphics_view_settings.zoom_settings.zoom_factor = value

    def _on_settings_zoom_factor_changed(self, value: float):
        self._zoom_factor_spin_box.setValue(value)


class ImageViewerSettingsPlugin(SettingsPlugin):
    def __init__(self, main_window_plugin: MainWindowPlugin):
        super().__init__(main_window_plugin, ImageViewerSettings)

    def _enable_gui(self):
        super()._enable_gui()

        # self._main_window.add_menu_action(SettingsMenu, 'Image Viewer', self._on_settings_menu_triggered)

    def _on_settings_menu_triggered(self):
        settings_widget = ImageViewerSettingsWidget(self._settings, self._main_window)
        settings_widget.show()
