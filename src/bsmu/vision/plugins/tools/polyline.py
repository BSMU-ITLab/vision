from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QEvent, QPointF, QLineF, QRectF, Signal
from PySide6.QtGui import QMouseEvent, QPainterPath, QPen, QBrush, QPainter, QCursor, QColor
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsItem

from bsmu.vision.core.utils.geometry import GeometryUtils
from bsmu.vision.plugins.tools import (
    ViewerToolPlugin, ViewerToolSettingsWidget, ViewerToolSettings, CursorConfig)
from bsmu.vision.plugins.tools.graphics import GraphicsViewerT, GraphicsViewerTool
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from PySide6.QtGui import QUndoCommand
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools import ViewerTool
    from bsmu.vision.plugins.undo import UndoManager, UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin
    from bsmu.vision.widgets.viewers.image.layered import LayeredImageViewer


@dataclass(frozen=True)
class ClosestPolylinePointInfo:
    point: QPointF | None = None
    segment_index: int | None = None
    squared_distance: float | None = None


class Polyline(QObject):
    point_appended = Signal(QPointF)
    end_point_removed = Signal(QPointF)

    def __init__(self):
        super().__init__()

        self._points: list[QPointF] = []

    @property
    def points(self) -> list[QPointF]:
        return self._points

    @property
    def end_point(self) -> QPointF:
        return self._points[-1]

    @property
    def is_empty(self) -> bool:
        return not self._points

    @property
    def length(self) -> float:
        if len(self._points) < 2:
            return 0.0

        return sum(
            GeometryUtils.distance(self._points[i], self._points[i + 1])
            for i in range(len(self._points) - 1)
        )

    def append_point(self, point: QPointF):
        self._points.append(point)
        self.point_appended.emit(point)

    def remove_end_point(self):
        if self._points:
            end_point = self._points.pop()
            self.end_point_removed.emit(end_point)

    def closest_point(self, point: QPointF) -> QPointF | None:
        """
        Returns the closest point on the polyline to the given point.
        Returns None if the polyline is empty.
        """
        return self._closest_point_info(point).point

    def closest_point_info(self, point: QPointF) -> ClosestPolylinePointInfo:
        """Returns the closest point with segment info, calculating distance if needed."""
        partial_closest_point_info = self._closest_point_info(point)
        if partial_closest_point_info.point is not None and partial_closest_point_info.squared_distance is None:
            return ClosestPolylinePointInfo(
                point=partial_closest_point_info.point,
                segment_index=partial_closest_point_info.segment_index,
                squared_distance=GeometryUtils.squared_distance(point, partial_closest_point_info.point),
            )
        return partial_closest_point_info

    def _closest_point_info(self, point: QPointF) -> ClosestPolylinePointInfo:
        """
        Internal implementation of closest point search.
        :return: ClosestPolylinePointInfo with:
            - For empty polylines: all None
            - For single-point polylines: (point, 0, None)
            - For normal cases: full results
        """
        if self.is_empty:
            return ClosestPolylinePointInfo()

        if len(self._points) == 1:
            return ClosestPolylinePointInfo(point=self.end_point, segment_index=0)

        closest_point: QPointF | None = None
        segment_index: int | None = None
        min_squared_distance: float = math.inf

        # Check each segment of the polyline
        for i in range(len(self._points) - 1):
            segment_start = self._points[i]
            segment_end = self._points[i + 1]

            segment_closest_point = GeometryUtils.closest_point_on_segment(segment_start, segment_end, point)
            squared_distance = GeometryUtils.squared_distance(point, segment_closest_point)

            if squared_distance < min_squared_distance:
                min_squared_distance = squared_distance
                closest_point = segment_closest_point
                segment_index = i

        return ClosestPolylinePointInfo(
            point=closest_point, segment_index=segment_index, squared_distance=min_squared_distance)


class NodeView(QGraphicsEllipseItem):
    def __init__(self, pos: QPointF, brush: QBrush = None, parent: QGraphicsItem = None):
        super().__init__(QRectF(-5, -5, 10, 10), parent)

        self.setPos(pos)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        if brush is not None:
            self.setBrush(brush)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


class PolylineView(QGraphicsPathItem):
    DEFAULT_FINISHED_COLOR = QColor(106, 255, 13)

    def __init__(self, polyline: Polyline, finished_color: QColor = None, parent: QGraphicsItem = None):
        super().__init__(parent)

        self._polyline = polyline
        self._polyline.point_appended.connect(self._on_point_appended)
        self._polyline.end_point_removed.connect(self._on_end_point_removed)

        self._finished_color = finished_color or self.DEFAULT_FINISHED_COLOR

        self._path = QPainterPath()
        self.setPath(self._path)

        pen = QPen(Qt.GlobalColor.blue, 3)
        pen.setCosmetic(True)
        self.setPen(pen)

        self._node_views: list[NodeView] = []

    @property
    def polyline(self) -> Polyline:
        return self._polyline

    @property
    def end_point(self) -> QPointF:
        return self._polyline.end_point

    def append_point(self, point: QPointF):
        self._polyline.append_point(point)

    def remove_end_point(self):
        self._polyline.remove_end_point()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)

    def finish_drawing(self):
        pen = self.pen()
        pen.setColor(self._finished_color)
        self.setPen(pen)

    def _on_point_appended(self, point: QPointF):
        if not self._path.elementCount():  # If no points exist, move to the first one
            self._path.moveTo(point)
        else:
            self._path.lineTo(point)
        self.setPath(self._path)

        node = NodeView(point, self._finished_color, self)
        self._node_views.append(node)

    def _on_end_point_removed(self):
        self._rebuild_path()

        end_node = self._node_views.pop()
        self.scene().removeItem(end_node)

    def _rebuild_path(self):
        self._path = QPainterPath()  # Avoid using self._path.clear(),
        # as it does not clear moveTo element in PySide 6.8.0.2
        if self._polyline.points:
            self._path.moveTo(self._polyline.points[0])
            for point in self._polyline.points[1:]:
                self._path.lineTo(point)
        self.setPath(self._path)


class AddPolylineViewCommand(UndoCommand):
    def __init__(
            self,
            viewer: LayeredImageViewer,  # TODO: Should work with any viewer, which contains QGraphicsScene
            polyline_view: PolylineView,
            first_point: QPointF,
            parent: QUndoCommand = None
    ):
        super().__init__(QObject.tr('Add Polyline'), parent)

        self._viewer = viewer
        self._polyline_view = polyline_view
        self._first_point = first_point

    def redo(self):
        self._viewer.add_graphics_item(self._polyline_view)
        self._polyline_view.append_point(self._first_point)

    def undo(self):
        if self._polyline_view.end_point is not self._first_point:
            raise ValueError('Last point of polyline does not match the expected point.')
        self._polyline_view.remove_end_point()

        self._viewer.remove_graphics_item(self._polyline_view)


class AddPolylinePointCommand(UndoCommand):
    def __init__(self, polyline: Polyline, point: QPointF, parent: QUndoCommand = None):
        super().__init__(QObject.tr('Add Polyline Point'), parent)

        self._polyline = polyline
        self._point = point

    def redo(self):
        self._polyline.append_point(self._point)

    def undo(self):
        if self._polyline.is_empty:
            raise ValueError('Polyline is empty. Cannot undo.')

        if self._polyline.end_point is not self._point:
            raise ValueError('End point does not match the point being undone.')

        self._polyline.remove_end_point()


class PreviewSegment(QGraphicsLineItem):
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)


class PolylineToolState(Enum):
    IDLE = 1     # When drawing is finished or never started
    DRAWING = 2  # When polyline drawing has started
    PAUSED = 3   # When switched to another tool while drawing


class PolylineViewerTool(GraphicsViewerTool):
    def __init__(self, viewer: GraphicsViewerT, undo_manager: UndoManager, settings: ViewerToolSettings):
        super().__init__(viewer, undo_manager, settings)

        self._curr_polyline: Polyline | None = None
        self._curr_polyline_view: PolylineView | None = None

        self._preview_segment: QGraphicsLineItem | None = None

        self._state = PolylineToolState.IDLE

    def activate(self):
        super().activate()

        self._resume_drawing()

        self.viewer.viewport.setMouseTracking(True)

    def deactivate(self):
        self._pause_drawing()

        self.viewer.viewport.setMouseTracking(False)

        super().deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if not isinstance(event, QMouseEvent):
            return super().eventFilter(watched_obj, event)

        event_type = event.type()
        match event_type:
            case QEvent.Type.MouseButtonPress:
                match event.button():
                    case Qt.MouseButton.LeftButton:
                        scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())
                        self._add_point(scene_pos)
                        return True
                    case Qt.MouseButton.RightButton:
                        self._finish_drawing()
                        return True
            case QEvent.Type.MouseMove:
                if self.is_drawing:
                    scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())
                    self._update_preview_segment(scene_pos)
                    return True
            case QEvent.Type.MouseButtonDblClick:
                if event.button() is Qt.MouseButton.LeftButton:
                    self._finish_drawing()
                    return True

        return super().eventFilter(watched_obj, event)

    @property
    def is_drawing(self) -> bool:
        return self._state is PolylineToolState.DRAWING

    def _add_point(self, pos: QPointF):
        if self._state is PolylineToolState.IDLE:
            self._start_new_polyline_drawing(pos)
        else:
            command = AddPolylinePointCommand(self._curr_polyline, pos)
            self._undo_manager.push(command)

            self._clear_preview_segment()

    def _start_new_polyline_drawing(self, pos: QPointF):
        self._curr_polyline = Polyline()
        self._curr_polyline_view = PolylineView(self._curr_polyline)

        add_polyline_view_command = AddPolylineViewCommand(self.viewer, self._curr_polyline_view, pos)
        self._undo_manager.push(add_polyline_view_command)

        self._create_preview_segment()

        self._curr_polyline.end_point_removed.connect(self._on_polyline_end_point_removed)

        self._state = PolylineToolState.DRAWING

    def _create_preview_segment(self):
        self._preview_segment = PreviewSegment()
        pen = self._curr_polyline_view.pen()
        pen.setColor(Qt.GlobalColor.red)
        self._preview_segment.setPen(pen)
        self.viewer.add_graphics_item(self._preview_segment)
        self._preview_segment.stackBefore(self._curr_polyline_view)

    def _clear_preview_segment(self):
        self._preview_segment.setLine(QLineF())
        self._preview_segment.hide()

    def _update_preview_segment(self, pos: QPointF):
        self._preview_segment.setLine(QLineF(self._curr_polyline.end_point, pos))
        self._show_preview_segment()

    def _update_preview_segment_to_cursor_pos(self):
        scene_pos = self.viewer.map_global_to_scene(QCursor.pos())
        self._update_preview_segment(scene_pos)

    def _on_polyline_end_point_removed(self, removed_point: QPointF):
        if self._curr_polyline.is_empty:
            self._finish_drawing()
            return

        if self.is_drawing:
            self._update_preview_segment_to_cursor_pos()

    def _show_preview_segment(self):
        if not self._preview_segment.isVisible():
            self._preview_segment.show()

    def _pause_drawing(self):
        if not self.is_drawing:
            return

        self._clear_preview_segment()

        self._state = PolylineToolState.PAUSED

    def _resume_drawing(self):
        if self._state is not PolylineToolState.PAUSED:
            return

        self._update_preview_segment_to_cursor_pos()

        self._state = PolylineToolState.DRAWING

    def _finish_drawing(self):
        if self._state is PolylineToolState.IDLE:
            return

        self._curr_polyline.end_point_removed.disconnect(self._on_polyline_end_point_removed)
        self.viewer.remove_graphics_item(self._preview_segment)
        self._preview_segment = None

        self._curr_polyline_view.finish_drawing()
        self._curr_polyline_view = None
        self._curr_polyline = None

        self._state = PolylineToolState.IDLE


POLYLINE_CURSOR_CONFIG = CursorConfig(
    icon_file_name=':/icons/polyline-cursor.svg',
    hot_x=0.278,
    hot_y=0.214,
)


class PolylineViewerToolSettings(ViewerToolSettings):
    def __init__(
            self,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig = POLYLINE_CURSOR_CONFIG,
            action_icon_file_name: str = ':/icons/polyline-action.svg',
    ):
        super().__init__(palette_pack_settings, cursor_config, action_icon_file_name)


class PolylineViewerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool] = PolylineViewerTool,
            tool_settings_cls: type[ViewerToolSettings] = PolylineViewerToolSettings,
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
