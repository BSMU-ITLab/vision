from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtGui import QMouseEvent, QCursor

from bsmu.vision.actors.shape import NodeBasedShapeActor
from bsmu.vision.actors.shape.constrained import SnappedSpanActor
from bsmu.vision.core.data.vector import Vector
from bsmu.vision.plugins.tools.layered import LayeredDataViewerTool
from bsmu.vision.undo.data.vector.shape import CreateNodeBasedShapeCommand

if TYPE_CHECKING:
    from PySide6.QtCore import QObject, QPointF

    from bsmu.vision.core.data.vector.shapes import NodeBasedShape
    from bsmu.vision.core.data.vector.shapes.constrained import SnappedSpan
    from bsmu.vision.plugins.undo import UndoManager
    from bsmu.vision.plugins.tools.layered import LayeredDataViewerToolSettings
    from bsmu.vision.widgets.viewers.layered import LayeredDataViewer


class SnappedSpanToolState(Enum):
    IDLE = auto()
    DRAWING = auto()
    PAUSED = auto()


class SnappedSpanFactory:
    """Abstract base factory for creating snapped spans."""
    def create_span(self, parent_shape: NodeBasedShape, **kwargs) -> SnappedSpan:
        raise NotImplementedError()

    def __call__(self, *args, **kwargs) -> SnappedSpan:
        return self.create_span(*args, **kwargs)


class SnappedSpanTool(LayeredDataViewerTool):
    """Tool for creating SnappedSpan annotations by clicking on a NodeBasedShape."""

    SNAP_SCREEN_TOLERANCE = 150.0  # TODO: Make this configurable (pass from config-file)

    span_creation_started = Signal(SnappedSpanActor)  # Emitted when first point is placed
    span_created = Signal(SnappedSpanActor)
    span_creation_cancelled = Signal()

    def __init__(
            self,
            span_factory: SnappedSpanFactory,
            viewer: LayeredDataViewer,
            undo_manager: UndoManager,
            settings: LayeredDataViewerToolSettings,
    ) -> None:
        super().__init__(viewer, undo_manager, settings)

        self._span_factory = span_factory

        self._state = SnappedSpanToolState.IDLE
        self._curr_span: SnappedSpan | None = None
        self._curr_vector: Vector | None = None
        self._parent_shape: NodeBasedShape | None = None
        self._drawing_undo_start_index: int | None = None

    @property
    def span_factory(self) -> SnappedSpanFactory:
        return self._span_factory

    @span_factory.setter
    def span_factory(self, value: SnappedSpanFactory) -> None:
        if self._span_factory is not value:
            self._span_factory = value

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

        scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())

        match event.type():
            case QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._handle_click(scene_pos)
                    return True
                if event.button() == Qt.MouseButton.RightButton:
                    self._cancel_drawing()
                    return True
            case QEvent.Type.MouseMove:
                if self._state is SnappedSpanToolState.DRAWING:
                    self._update_end_node_position(scene_pos)
                    return True

        return super().eventFilter(watched_obj, event)

    def _handle_click(self, scene_pos: QPointF) -> None:
        if self._state is SnappedSpanToolState.IDLE:
            self._start_new_span(scene_pos)
        elif self._state is SnappedSpanToolState.DRAWING:
            self._update_end_node_position(scene_pos)
            self._complete_span()

    def _start_new_span(self, start_pos: QPointF) -> None:
        """Initialize a new span by projecting the start position onto a valid parent shape."""
        parent_actor = self.viewer.vector_actor_near(
            start_pos,
            screen_tolerance=self.SNAP_SCREEN_TOLERANCE,
            predicate=lambda a: isinstance(a, NodeBasedShapeActor) and not isinstance(a, SnappedSpanActor),
        )

        if not isinstance(parent_actor, NodeBasedShapeActor):
            return

        self._parent_shape = parent_actor.shape

        hit_info = self._parent_shape.closest_edge(start_pos)
        if hit_info is None or hit_info.closest_point is None:
            return

        self._drawing_undo_start_index = self._undo_manager.index()

        self._curr_vector = self._parent_shape.parent()
        assert isinstance(self._curr_vector, Vector), 'Parent of shape must be a Vector'

        self.selection_manager.clear_selection()

        create_span_command = CreateNodeBasedShapeCommand(
            layered_data=self.viewer.data,
            vector=self._curr_vector,
            shape_creator=self._span_factory,
            points=[],  # Positions set explicitly after creation
            parent_shape=self._parent_shape,
            text='Create Snapped Span',
        )
        self._undo_manager.push(create_span_command)
        self._curr_span = create_span_command.created_shape

        start_local = self._curr_span.scene_to_local(hit_info.closest_point)
        self._curr_span.start_node.local_pos = start_local

        self._update_end_node_position(start_pos)

        self._curr_vector.shape_removed.connect(self._on_vector_shape_removed)

        self._state = SnappedSpanToolState.DRAWING

    def _update_end_node_position(self, cursor_pos: QPointF) -> None:
        """Update the end node position by projecting the cursor onto the parent shape."""
        if self._curr_span is None or self._parent_shape is None:
            return

        hit_info = self._parent_shape.closest_edge(cursor_pos)
        if hit_info is None or hit_info.closest_point is None:
            return

        local_point = self._curr_span.scene_to_local(hit_info.closest_point)
        self._curr_span.end_node.local_pos = local_point

    def _complete_span(self) -> None:
        if self._state is SnappedSpanToolState.IDLE:
            return

        self._curr_span.complete()
        self.viewer.selection_manager.select_shape(self._curr_span)
        self._reset_tool_state()

    def _cancel_drawing(self) -> None:
        if self._state is SnappedSpanToolState.DRAWING:
            self._undo_manager.undo()
            # Note: State reset is intentionally handled by the undo command's side effects.

    def _reset_tool_state(self) -> None:
        if self._state is SnappedSpanToolState.IDLE:
            return

        if self._curr_span is not None:
            self._curr_vector.shape_removed.disconnect(self._on_vector_shape_removed)

        self._curr_span = None
        self._curr_vector = None
        self._parent_shape = None
        self._drawing_undo_start_index = None
        self._state = SnappedSpanToolState.IDLE

    def _update_end_node_to_cursor(self) -> None:
        """Update the end node position based on the current global cursor position."""
        if self._curr_span is not None:
            scene_pos = self.viewer.map_global_to_scene(QCursor.pos())
            self._update_end_node_position(scene_pos)

    def _on_vector_shape_removed(self, shape: NodeBasedShape) -> None:
        if shape is self._curr_span:
            self._reset_tool_state()
            QTimer.singleShot(0, self._discard_draft_undo_commands)

    def _discard_draft_undo_commands(self) -> None:
        """Discard undo commands generated by the current span creation."""
        if self._drawing_undo_start_index is not None:
            self._undo_manager.discard_commands_after(self._drawing_undo_start_index)
            self._drawing_undo_start_index = None

    def _pause_drawing(self) -> None:
        if self._state is not SnappedSpanToolState.DRAWING:
            return
        self._state = SnappedSpanToolState.PAUSED

    def _resume_drawing(self) -> None:
        if self._state is SnappedSpanToolState.PAUSED:
            self._state = SnappedSpanToolState.DRAWING
            self._update_end_node_to_cursor()
