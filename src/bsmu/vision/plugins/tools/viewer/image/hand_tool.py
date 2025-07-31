from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject

from bsmu.vision.plugins.tools.viewer import (
    ViewerToolPlugin, ViewerToolSettingsWidget, ViewerTool, ViewerToolSettings, CursorConfig)

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.undo import UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin


class HandImageViewerTool(ViewerTool):
    pass


class HandImageViewerToolSettings(ViewerToolSettings):
    def __init__(
            self,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig = CursorConfig(),
            action_icon_file_name: str = ':/icons/hand.svg',
    ):
        super().__init__(palette_pack_settings, cursor_config, action_icon_file_name)


class HandImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: Type[ViewerTool] = HandImageViewerTool,
            tool_settings_cls: Type[ViewerToolSettings] = HandImageViewerToolSettings,
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget] = None,
            action_name: str = QObject.tr('Hand'),
            action_shortcut: Qt.Key = Qt.Key_1,
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
