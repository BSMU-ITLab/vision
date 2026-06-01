from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent, QKeyEvent

from bsmu.vision.actors.shape import NodeBasedShapeActor
from bsmu.vision.actors.shape import VectorShapeActor, VectorNodeActor, VectorElementActor
from bsmu.vision.core.data.vector.shapes import VectorShape, VectorNode, BaseShapeState
from bsmu.vision.plugins.tools import (
    ViewerToolPlugin, ViewerToolSettingsWidget, ViewerToolSettings, CursorConfig)
from bsmu.vision.plugins.tools.layered import LayeredDataViewerTool, LayeredDataViewerToolSettings
from bsmu.vision.undo.data.vector.shape import (
    InsertNodeCommand, MoveShapesCommand, MoveNodesCommand, RemoveShapesCommand, DeleteNodesCommand)
from bsmu.vision.widgets.viewers.layered import LayeredDataViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
    from bsmu.vision.plugins.palette.settings import PalettePackSettings, PalettePackSettingsPlugin
    from bsmu.vision.plugins.tools import ViewerTool
    from bsmu.vision.plugins.undo import UndoManager, UndoPlugin
    from bsmu.vision.plugins.windows.main import MainWindowPlugin

GrabValue = QPointF | float


DOUBLE_CLICK_SCREEN_TOLERANCE = 10.0


class PointerToolMode(Enum):
    IDLE = auto()
    MOVING_SHAPES = auto()
    MOVING_NODES = auto()


class PointerTool(LayeredDataViewerTool):
    """
    A unified tool for selecting, moving, and editing vector shapes and their nodes.

    Designed for intuitive direct manipulation - ideal for non-technical users (e.g., clinicians).
    Supports single and multi-selection of shapes and nodes via Shift, with visual feedback.

    Interaction Summary:

    **Selection**
    - Click on empty canvas -> deselect all shapes and nodes.
    - Click on a shape (not on a node) -> select that shape; deselect others.
    - Shift + click on a shape -> toggle its selection (add/remove from current selection).
    - Click on a node -> select that node; deselect others.
    - Shift + click on a node -> toggle node selection.

    **Editing**
    - Drag a selected shape -> move all selected shapes together.
    - Drag a selected node -> move all selected nodes (within their respective shapes).
    - Double-click on shape edge -> insert node at closest point.
      Selects the new node (Shift to toggle selection).
    - Press Delete -> remove selected shapes and nodes.
    """

    def __init__(
            self,
            viewer: LayeredDataViewer,
            undo_manager: UndoManager,
            settings: LayeredDataViewerToolSettings,
    ):
        super().__init__(viewer, undo_manager, settings)

        self._mode = PointerToolMode.IDLE

        self._drag_start_pos: QPointF | None = None
        self._pressed_actor: VectorElementActor | None = None

        self._dragged_nodes: frozenset[VectorNode] | None = None
        self._node_to_initial_local_pos: dict[VectorNode, QPointF] = {}
        self._move_nodes_command: MoveNodesCommand | None = None

        self._dragged_shapes: frozenset[VectorShape] | None = None
        self._shape_to_grab_value: dict[VectorShape, GrabValue] = {}
        self._shape_to_initial_state: dict[VectorShape, BaseShapeState] = {}
        self._move_shapes_command: MoveShapesCommand | None = None

    def deactivate(self) -> None:
        self._exit_drag_mode()
        super().deactivate()

    def eventFilter(self, watched_obj: QObject, event: QEvent) -> bool:
        if isinstance(event, QMouseEvent):
            return self._handle_mouse_event(event)
        elif isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            return self._handle_key_event(event)
        return super().eventFilter(watched_obj, event)

    def _handle_mouse_event(self, event: QMouseEvent) -> bool:
        scene_pos = self.viewer.map_viewport_to_scene(event.position().toPoint())

        match event.type():
            case QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    return self._on_mouse_press(scene_pos, event.modifiers())
            case QEvent.Type.MouseMove:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    return self._on_mouse_drag(scene_pos)
            case QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    return self._on_mouse_release()
            case QEvent.Type.MouseButtonDblClick:
                if event.button() == Qt.MouseButton.LeftButton:
                    return self._on_double_click(scene_pos, event.modifiers())

        return False

    def _handle_key_event(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Delete:
            return self._delete_selected()
        return False

    def _on_mouse_press(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> bool:
        actor = self.viewer.vector_actor_near(scene_pos)
        is_multi_select = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if actor is None:
            if is_multi_select:
                return False
            else:
                self._clear_selection()
                return True

        if isinstance(actor, VectorShapeActor):
            if is_multi_select:
                self.selection_manager.toggle_shape_selection(actor.shape)
            else:
                self.selection_manager.select_shape(actor.shape)
        elif isinstance(actor, VectorNodeActor):
            if is_multi_select:
                self.selection_manager.toggle_node_selection(actor.node)
            else:
                self.selection_manager.select_node(actor.node)

        self._drag_start_pos = scene_pos
        self._pressed_actor = actor

        self._node_to_initial_local_pos = {node: node.local_pos for node in self.selection_manager.selected_nodes}

        self._shape_to_grab_value.clear()
        self._shape_to_initial_state.clear()
        for shape in self.selection_manager.selected_shapes:
            self._shape_to_grab_value[shape] = shape.calculate_grab_value(scene_pos)
            self._shape_to_initial_state[shape] = shape.capture_state()

        return True

    def _clear_selection(self) -> None:
        self.selection_manager.clear_selection()

    def _on_mouse_drag(self, scene_pos: QPointF) -> bool:
        if self._pressed_actor is None:
            return False

        if self._mode == PointerToolMode.IDLE:
            if isinstance(self._pressed_actor, VectorShapeActor):
                self._enter_shape_drag_mode()
            elif isinstance(self._pressed_actor, VectorNodeActor):
                self._enter_node_drag_mode()

        match self._mode:
            case PointerToolMode.MOVING_SHAPES:
                self._drag_shapes_live(scene_pos)
            case PointerToolMode.MOVING_NODES:
                self._drag_nodes_live(scene_pos)

        return True

    def _enter_shape_drag_mode(self) -> None:
        self._mode = PointerToolMode.MOVING_SHAPES
        self._dragged_shapes = self.selection_manager.selected_shapes

        self._move_shapes_command = MoveShapesCommand(
            self.viewer.data, self._dragged_shapes, self._shape_to_initial_state)

    def _enter_node_drag_mode(self) -> None:
        self._mode = PointerToolMode.MOVING_NODES
        self._dragged_nodes = self.selection_manager.selected_nodes

        self._move_nodes_command = MoveNodesCommand(
            self.viewer.data,
            self._dragged_nodes,
            self._node_to_initial_local_pos,
        )

    def _drag_nodes_live(self, cursor_scene_pos: QPointF) -> None:
        if not self._dragged_nodes:
            return

        for node in self._dragged_nodes:
            node.update_drag_position(
                cursor_scene_pos,
                self._node_to_initial_local_pos[node],
                self._drag_start_pos,
            )

    def _drag_shapes_live(self, cursor_scene_pos: QPointF) -> None:
        if not self._dragged_shapes:
            return

        for shape in self._dragged_shapes:
            grab_value = self._shape_to_grab_value[shape]
            new_grab_value = shape.apply_drag(cursor_scene_pos, grab_value)
            self._shape_to_grab_value[shape] = new_grab_value

    def _on_mouse_release(self) -> bool:
        match self._mode:
            case PointerToolMode.MOVING_NODES:
                if self._move_nodes_command and self._move_nodes_command.has_changes:
                    self._undo_manager.push(self._move_nodes_command)
            case PointerToolMode.MOVING_SHAPES:
                if self._move_shapes_command and self._move_shapes_command.has_changes:
                    self._undo_manager.push(self._move_shapes_command)

        self._exit_drag_mode()
        return True

    def _exit_drag_mode(self) -> None:
        self._mode = PointerToolMode.IDLE
        self._drag_start_pos = None
        self._pressed_actor = None

        self._dragged_nodes = None
        self._node_to_initial_local_pos.clear()
        self._move_nodes_command = None

        self._dragged_shapes = None
        self._shape_to_grab_value.clear()
        self._shape_to_initial_state.clear()
        self._move_shapes_command = None

    def _on_double_click(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> bool:
        return self._try_insert_node_on_edge(scene_pos, modifiers)

    def _try_insert_node_on_edge(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> bool:
        # Find nearest actor
        actor = self.viewer.vector_actor_near(scene_pos)
        if not isinstance(actor, NodeBasedShapeActor):
            return False

        # Find the closest edge within reasonable tolerance
        shape = actor.shape
        scene_tolerance = self.viewer.screen_to_scene_tolerance(DOUBLE_CLICK_SCREEN_TOLERANCE)
        hit_info = shape.closest_edge(scene_pos, max_tolerance=scene_tolerance)
        if hit_info is None:
            return False

        # Insert node & push undo command
        insert_index = hit_info.edge_index + 1  # Insert between the two edge nodes
        insert_node_command = InsertNodeCommand(
            layered_data=self.viewer.data,
            shape=shape,
            pos=hit_info.closest_point,
            index=insert_index,
            text=f'Insert Node in {type(shape).__name__}'
        )
        self._undo_manager.push(insert_node_command)

        # Auto-select the newly created node (respects Shift modifier)
        new_node = shape.nodes[insert_index]
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.selection_manager.toggle_node_selection(new_node)
            # Revert shape toggle from preceding press (Qt fires press before double-click)
            self.selection_manager.toggle_shape_selection(shape)
        else:
            self.selection_manager.select_node(new_node)

        return True

    def _ensure_shape_selected_for_edit(
            self,
            shape: VectorShape,
            modifiers: Qt.KeyboardModifier,
    ) -> None:
        """Select the shape if not already selected, preserving Shift behavior."""
        if shape in self.selection_manager.selected_shapes:
            return

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.selection_manager.toggle_shape_selection(shape)
        else:
            self.selection_manager.select_shape(shape)

    def _delete_selected(self) -> bool:
        selected_shapes = set(self.selection_manager.selected_shapes)
        selected_nodes = set(self.selection_manager.selected_nodes)

        if not selected_shapes and not selected_nodes:
            return False

        # Filter out nodes that belong to shapes being deleted to avoid double-deletion
        nodes_to_delete = [n for n in selected_nodes if n.parent_shape not in selected_shapes]

        self._undo_manager.begin_macro('Delete Selected')

        if selected_shapes:
            delete_shapes_command = RemoveShapesCommand(self.viewer.data, selected_shapes, 'Delete Shapes')
            self._undo_manager.push(delete_shapes_command)

        if nodes_to_delete:
            delete_nodes_command = DeleteNodesCommand(self.viewer.data, nodes_to_delete)
            self._undo_manager.push(delete_nodes_command)

        self._undo_manager.end_macro()

        return True


POINTER_CURSOR_CONFIG = CursorConfig(
    icon_file_name=':/icons/pointer-cursor.svg',
    hot_x=0.332,
    hot_y=0.204,
)


class PointerToolSettings(LayeredDataViewerToolSettings):
    def __init__(
            self,
            layers_props: dict,
            palette_pack_settings: PalettePackSettings,
            cursor_config: CursorConfig = POINTER_CURSOR_CONFIG,
            action_icon_file_name: str = ':/icons/pointer-action.svg',
    ):
        super().__init__(layers_props, palette_pack_settings, cursor_config, action_icon_file_name)


class PointerToolPlugin(ViewerToolPlugin):
    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            mdi_plugin: MdiPlugin,
            undo_plugin: UndoPlugin,
            palette_pack_settings_plugin: PalettePackSettingsPlugin,
            tool_cls: type[ViewerTool] = PointerTool,
            tool_settings_cls: type[ViewerToolSettings] = PointerToolSettings,
            tool_settings_widget_cls: type[ViewerToolSettingsWidget] = None,
            action_name: str = QObject.tr('Pointer'),
            action_shortcut: Qt.Key = Qt.Key.Key_3,
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
