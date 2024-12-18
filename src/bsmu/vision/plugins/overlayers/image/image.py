from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog

from bsmu.vision.core.palette import Palette
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.visibility import Visibility
from bsmu.vision.plugins.windows.main import FileMenu
from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewerHolder

if TYPE_CHECKING:
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin, PalettePackSettings
    from bsmu.vision.plugins.readers.manager import FileReadingManagerPlugin, FileReadingManager
    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow


class ImageViewerOverlayerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_reading_manager_plugin': 'bsmu.vision.plugins.readers.manager.FileReadingManagerPlugin',
        'palette_pack_settings_plugin': 'bsmu.vision.plugins.palette.settings.PalettePackSettingsPlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            file_reading_manager_plugin: FileReadingManagerPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_reading_manager_plugin = file_reading_manager_plugin
        self._file_reading_manager: FileReadingManager | None = None

        self._palette_pack_settings_plugin = palette_pack_settings_plugin
        self._palette_pack_settings: PalettePackSettings | None = None

        self._last_opened_file_dir = None

    def _enable(self):
        self._file_reading_manager = self._file_reading_manager_plugin.file_reading_manager
        self._palette_pack_settings = self._palette_pack_settings_plugin.settings

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
        if not layered_image_viewer.is_confirmed_repaint_duplicate_mask_layer(layer_name):
            return

        mask_props = layers_props.get(layer_name)
        mask_palette = Palette.from_config(mask_props.get('palette'))
        if mask_palette is None:
            mask_palette = self._palette_pack_settings.main_palette
        mask = self._file_reading_manager.read_file(Path(file_name), palette=mask_palette)

        mask_opacity = mask_props.get('opacity')
        mask_visibility = None if mask_opacity is None else Visibility(opacity=mask_opacity)
        layered_image_viewer.add_layer_or_modify_image(layer_name, mask, visibility=mask_visibility)
