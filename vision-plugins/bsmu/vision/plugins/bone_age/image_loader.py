from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QFileDialog

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import FileMenu

if TYPE_CHECKING:
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.loaders.image.simple import SimpleImageFileLoaderPlugin, SimpleImageFileLoader
    from bsmu.vision.plugins.post_load_converters.manager import PostLoadConversionManagerPlugin, \
        PostLoadConversionManager


class ImageLoaderPlugin(Plugin):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'simple_image_file_loader_plugin': 'bsmu.vision.plugins.loaders.image.simple.SimpleImageFileLoaderPlugin',
        'post_load_conversion_manager_plugin':
            'bsmu.vision.plugins.post_load_converters.manager.PostLoadConversionManagerPlugin',
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            simple_image_file_loader_plugin: SimpleImageFileLoaderPlugin,
            post_load_conversion_manager_plugin: PostLoadConversionManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._simple_image_file_loader_plugin = simple_image_file_loader_plugin
        self._simple_image_file_loader: SimpleImageFileLoader | None = None

        self._post_load_conversion_manager_plugin = post_load_conversion_manager_plugin
        self._post_load_conversion_manager: PostLoadConversionManager | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._simple_image_file_loader = self._simple_image_file_loader_plugin.processor_cls()
        self._post_load_conversion_manager = self._post_load_conversion_manager_plugin.post_load_conversion_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        self._main_window.add_menu_action(FileMenu, 'Load...', self._show_image_load_dialog, Qt.CTRL + Qt.Key_O)

    def _show_image_load_dialog(self):
        file_path_strings, selected_filter = QFileDialog.getOpenFileNames(
            self._main_window, 'Open File', filter='Images (*.png *.jpg *.bmp)')
        for file_path_str in file_path_strings:
            image_data = self._simple_image_file_loader.load_file(Path(file_path_str))
            image_data = self._post_load_conversion_manager.convert_data(image_data)
            self._data_visualization_manager.visualize_data(image_data)
