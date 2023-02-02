from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog

from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.windows.main import FileMenu
from bsmu.vision.widgets.viewers.image.layered.base import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class ImageViewerOverlayerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._last_opened_file_dir = None

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._main_window.add_menu_action(FileMenu, 'Overlay Mask...', self._load_mask_and_overlay)

        self._mdi = self._mdi_plugin.mdi

    def _disable(self):
        raise NotImplementedError

    def _load_mask_and_overlay(self):
        layered_image_viewer_sub_window = self._mdi.active_sub_window_with_type(LayeredImageViewerHolder)
        if layered_image_viewer_sub_window is None:
            return

        layered_image_viewer = layered_image_viewer_sub_window.layered_image_viewer
        if self._last_opened_file_dir is None:
            dialog_dir = layered_image_viewer.active_layer.path
        else:
            dialog_dir = self._last_opened_file_dir
        dialog_dir_str = '' if dialog_dir is None else str(dialog_dir)
        file_name, selected_filter = QFileDialog.getOpenFileName(
            parent=self._main_window, caption='Load Mask', dir=dialog_dir_str, filter='PNG (*.png)')
        if not file_name:
            return
        self._last_opened_file_dir = Path(file_name).parent

        layers_props = self.config.value('layers')
        layer_name = 'masks'
        mask_props = layers_props.get(layer_name)
        mask_palette = Palette.from_config(mask_props.get('palette'))
        mask = self._file_loading_manager.load_file(Path(file_name), palette=mask_palette)

        mask_layer = layered_image_viewer.add_layer_from_image(mask, layer_name)

        mask_opacity = mask_props.get('opacity')
        if mask_opacity is not None:
            layered_image_viewer.layer_view_by_model(mask_layer).opacity = mask_opacity
