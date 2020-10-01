from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFileDialog

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.windows.main import FileMenu

if TYPE_CHECKING:
    from bsmu.vision.app import App


class ImageLoaderPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.simple_image_file_loader = app.enable_plugin(
            'bsmu.vision.plugins.loaders.image.simple.SimpleImageFileLoaderPlugin').file_loader_cls()
        self.post_load_conversion_manager = app.enable_plugin(
            'bsmu.vision.plugins.post_load_converters.manager.PostLoadConversionManagerPlugin').post_load_conversion_manager
        self.data_visualization_manager = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin').data_visualization_manager

    def _enable(self):
        self.main_window.add_menu_action(FileMenu, 'Load...', self._show_image_load_dialog, Qt.CTRL + Qt.Key_O)

    def _show_image_load_dialog(self):
        file_path_strings, selected_filter = QFileDialog.getOpenFileNames(
            self.main_window, 'Open File', filter='Images (*.png *.jpg)')
        for file_path_str in file_path_strings:
            image_data = self.simple_image_file_loader.load_file(Path(file_path_str))
            image_data = self.post_load_conversion_manager.convert_data(image_data)
            self.data_visualization_manager.visualize_data(image_data)
