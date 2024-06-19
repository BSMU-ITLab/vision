from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject

from bsmu.vision.plugins.tools.viewer.base import (
    ViewerToolPlugin, ViewerToolSettingsWidget,
    ViewerTool, ViewerToolSettings,
)

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettingsPlugin
    from bsmu.vision.plugins.undo import UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin


class PointerImageViewerTool(ViewerTool):
    ...


class PointerImageViewerToolSettings(ViewerToolSettings):
    ...


class PointerImageViewerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: Type[ViewerTool] = PointerImageViewerTool,
            tool_settings_cls: Type[ViewerToolSettings] = PointerImageViewerToolSettings,
            tool_settings_widget_cls: Type[ViewerToolSettingsWidget] = None,
            action_name: str = QObject.tr('Pointer'),
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
