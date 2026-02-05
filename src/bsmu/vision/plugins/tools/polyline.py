from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QEvent, QLineF
from PySide6.QtGui import QMouseEvent, QPen, QPainter, QCursor
from PySide6.QtWidgets import QGraphicsLineItem

from bsmu.vision.core.layers import VectorLayer
from bsmu.vision.plugins.tools import (
    ViewerToolPlugin, ViewerToolSettingsWidget, CursorConfig)
from bsmu.vision.plugins.tools.layered import LayeredDataViewerTool, LayeredDataViewerToolSettings
from bsmu.vision.undo.data.vector.polyline import CreatePolylineCommand, AddPolylineNodeCommand
from bsmu.vision.undo.layer import CreateVectorLayerCommand

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from bsmu.vision.core.data.vector.shapes import Polyline, VectorNode
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools import ViewerTool, ViewerToolSettings
    from bsmu.vision.plugins.undo import UndoManager, UndoPlugin
    from bsmu.vision.widgets.viewers.layered import LayeredDataViewer
    from bsmu.vision.plugins.windows.main import MainWindowPlugin


class PreviewSegment(QGraphicsLineItem):
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None) -> None:
        if self.line().isNull():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


class PolylineToolState(Enum):
    IDLE = 1     # When drawing is completed or never started
    DRAWING = 2  # When polyline drawing has started
    PAUSED = 3   # When switched to another tool while drawing


class PolylineTool(LayeredDataViewerTool):
    def __init__(
            self,
            viewer: LayeredDataViewer,
            undo_manager: UndoManager,
            settings: LayeredDataViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

        self._curr_polyline: Polyline | None = None

        self._preview_segment: QGraphicsLineItem | None = None

        self._state = PolylineToolState.IDLE

    def activate(self) -> None:
        super().activate()

        self._resume_drawing()

        self.viewer.viewport.setMouseTracking(True)

    def deactivate(self) -> None:
        self._pause_drawing()

        self.viewer.viewport.setMouseTracking(False)

        super().deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent) -> bool:
        if not isinstance(event, QMouseEvent):
            return super().eventFilter(watched_obj, event)

        match event.type():
            case QEvent.Type.MouseButtonPress:
                match event.button():
                    case Qt.MouseButton.LeftButton:
                        scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())
                        self._add_point(scene_pos)
                        return True
                    case Qt.MouseButton.RightButton:
                        self._complete_drawing()
                        return True
            case QEvent.Type.MouseMove:
                if self.is_drawing:
                    scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())
                    self._update_preview_segment(scene_pos)
                    return True
            case QEvent.Type.MouseButtonDblClick:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._complete_drawing()
                    return True

        return super().eventFilter(watched_obj, event)

    @property
    def is_drawing(self) -> bool:
        return self._state is PolylineToolState.DRAWING

    def _add_point(self, pos: QPointF) -> None:
        if self._state is PolylineToolState.IDLE:
            self._start_new_polyline_drawing(pos)
        else:
            command = AddPolylineNodeCommand(self._curr_polyline, pos)
            self._undo_manager.push(command)

            self._clear_preview_segment()

    def _start_new_polyline_drawing(self, pos: QPointF) -> None:
        self._undo_manager.begin_macro('Create Polyline')
        vector_layer_name = self.settings.vector_layer_name
        create_vector_layer_command = CreateVectorLayerCommand(self.viewer.data, vector_layer_name)
        self._undo_manager.push(create_vector_layer_command)
        vector_layer = self.viewer.layer_by_name(vector_layer_name)
        assert vector_layer is not None and isinstance(vector_layer, VectorLayer)
        assert vector_layer.data is not None
        create_polyline_command = CreatePolylineCommand(vector_layer.data, pos)
        self._undo_manager.push(create_polyline_command)
        self._curr_polyline = create_polyline_command.created_polyline
        self._undo_manager.end_macro()

        self._create_preview_segment()

        self._curr_polyline.last_node_removed.connect(self._on_polyline_last_node_removed)

        self._state = PolylineToolState.DRAWING

    def _create_preview_segment(self) -> None:
        self._preview_segment = PreviewSegment()
        pen = QPen(Qt.GlobalColor.red, 3)
        pen.setCosmetic(True)
        self._preview_segment.setPen(pen)
        self.viewer.add_graphics_item(self._preview_segment)

    def _clear_preview_segment(self) -> None:
        self._preview_segment.setLine(QLineF())
        self._preview_segment.hide()

    def _update_preview_segment(self, pos: QPointF) -> None:
        self._preview_segment.setLine(QLineF(self._curr_polyline.last_node.pos, pos))
        self._show_preview_segment()

    def _update_preview_segment_to_cursor_pos(self) -> None:
        scene_pos = self.viewer.map_global_to_scene(QCursor.pos())
        self._update_preview_segment(scene_pos)

    def _on_polyline_last_node_removed(self, _removed_node: VectorNode) -> None:
        if self._curr_polyline.is_empty:
            self._complete_drawing()
            return

        if self.is_drawing:
            self._update_preview_segment_to_cursor_pos()

    def _show_preview_segment(self) -> None:
        if not self._preview_segment.isVisible():
            self._preview_segment.show()

    def _pause_drawing(self) -> None:
        if not self.is_drawing:
            return

        self._clear_preview_segment()

        self._state = PolylineToolState.PAUSED

    def _resume_drawing(self) -> None:
        if self._state is not PolylineToolState.PAUSED:
            return

        self._update_preview_segment_to_cursor_pos()

        self._state = PolylineToolState.DRAWING

    def _complete_drawing(self) -> None:
        if self._state is PolylineToolState.IDLE:
            return

        self._curr_polyline.last_node_removed.disconnect(self._on_polyline_last_node_removed)
        self.viewer.remove_graphics_item(self._preview_segment)
        self._preview_segment = None

        self._curr_polyline.complete()
        self._curr_polyline = None

        self._state = PolylineToolState.IDLE


POLYLINE_CURSOR_CONFIG = CursorConfig(
    icon_file_name=':/icons/polyline-cursor.svg',
    hot_x=0.278,
    hot_y=0.214,
)


class PolylineToolSettings(LayeredDataViewerToolSettings):
    def __init__(
            self,
            layers_props: dict,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig = POLYLINE_CURSOR_CONFIG,
            action_icon_file_name: str = ':/icons/polyline-action.svg',
    ):
        super().__init__(layers_props, palette_pack_settings, cursor_config, action_icon_file_name)


class PolylineToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool] = PolylineTool,
            tool_settings_cls: type[ViewerToolSettings] = PolylineToolSettings,
            tool_settings_widget_cls: type[ViewerToolSettingsWidget] = None,
            action_name: str = QObject.tr('Polyline'),
            action_shortcut: Qt.Key = Qt.Key.Key_6,
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
