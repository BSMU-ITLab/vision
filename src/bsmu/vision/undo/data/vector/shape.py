from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import NamedTuple, TypeVar, Generic, TYPE_CHECKING

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.data.vector.shapes import NodeBasedShape
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from typing import Callable, Iterable, Sequence

    from bsmu.vision.core.data.layered import LayeredData
    from bsmu.vision.core.data.vector.shapes import VectorNode, VectorShape, BaseShapeState


NodeBasedShapeT = TypeVar('NodeBasedShapeT', bound=NodeBasedShape)

class CreateNodeBasedShapeCommand(UndoCommand, Generic[NodeBasedShapeT]):
    """Generic command to create any NodeBasedShape."""

    def __init__(
            self,
            layered_data: LayeredData,
            vector: Vector,
            shape_creator: Callable[..., NodeBasedShapeT],
            points: Sequence[QPointF],
            origin: QPointF | None = None,
            parent_shape: VectorShape | None = None,
            text: str | None = None,
            parent: UndoCommand | None = None,
    ):
        default_text = f'Create {getattr(shape_creator, "__name__", shape_creator.__class__.__name__)}'
        super().__init__(text or default_text, parent)

        self._layered_data = layered_data
        self._vector = vector
        self._shape_creator = shape_creator
        self._points = points
        self._origin = origin
        self._parent_shape = parent_shape

        self._shape: NodeBasedShapeT | None = None
        self._shape_handle: int | None = None
        self._node_handles: list[int] = []

    @property
    def created_shape(self) -> NodeBasedShapeT:
        if self._shape is None:
            raise RuntimeError('Command must be executed before accessing result.')
        return self._shape

    @property
    def created_shape_handle(self) -> int:
        if self._shape_handle is None:
            raise RuntimeError('Handle not assigned. Command must be executed first.')
        return self._shape_handle

    def redo(self) -> None:
        # Lazy creation: reuse instance across undo/redo cycles
        if self._shape is None:
            self._shape = self._shape_creator(
                points=self._points, origin=self._origin, parent_shape=self._parent_shape)

        self._vector.add_shape(self._shape)  # Signals auto-register shape + initial nodes

        # Stabilize shape handle
        self._shape_handle = self._layered_data.shape_registry.register(self._shape, self._shape_handle)

        # Stabilize initial node handles
        if not self._node_handles:
            # First run: capture auto-assigned handles
            self._node_handles = [
                self._layered_data.node_registry.get_handle(node)
                for node in self._shape.nodes
            ]
        else:
            # Subsequent redos: reclaim saved handles
            for i, node in enumerate(self._shape.nodes):
                self._layered_data.node_registry.register(node, self._node_handles[i])

    def undo(self) -> None:
        assert self._shape is not None

        self._vector.remove_shape(self._shape)  # Signals auto-unregister shape + nodes
        # Handles preserved in _shape_handle and _node_handles for next redo cycle


class MoveShapesCommand(UndoCommand):
    def __init__(
        self,
        layered_data: LayeredData,
        shapes: Iterable[VectorShape],
        shape_to_initial_state: dict[VectorShape, BaseShapeState],
        text: str = 'Move Shapes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._shape_handles: list[int] = []
        self._shape_handle_to_initial_state: dict[int, BaseShapeState] = {}
        self._shape_handle_to_final_state: dict[int, BaseShapeState] = {}
        self._is_final_states_captured = False

        for shape in shapes:
            handle = layered_data.shape_registry.get_handle(shape)
            if handle is None:
                raise ValueError(f'Shape {type(shape).__name__} is not registered.')
            self._shape_handles.append(handle)

        for shape, state in shape_to_initial_state.items():
            handle = layered_data.shape_registry.get_handle(shape)
            if handle is not None:
                self._shape_handle_to_initial_state[handle] = replace(state)

    @property
    def has_changes(self) -> bool:
        for handle in self._shape_handles:
            initial_state = self._shape_handle_to_initial_state.get(handle)
            shape = self._layered_data.shape_registry.resolve(handle)
            if shape:
                current_state = shape.capture_state()
                if initial_state != current_state:
                    return True
        return False

    def redo(self) -> None:
        if not self._is_final_states_captured:
            # First redo: capture current model states as final but don't apply
            for handle in self._shape_handles:
                shape = self._layered_data.shape_registry.resolve(handle)
                if shape:
                    self._shape_handle_to_final_state[handle] = shape.capture_state()
            self._is_final_states_captured = True
            return  # Model already in final state after live drag

        # Subsequent redos: apply final states
        self._apply_states(self._shape_handle_to_final_state)

    def undo(self) -> None:
        self._apply_states(self._shape_handle_to_initial_state)

    def _apply_states(self, states: dict[int, BaseShapeState]) -> None:
        """Apply given states to all tracked shapes."""
        for handle, state in states.items():
            shape = self._layered_data.shape_registry.resolve(handle)
            if shape:
                shape.restore_state(state)

    def id(self) -> int:
        return self.command_type_id()

    def mergeWith(self, other: UndoCommand) -> bool:
        if not isinstance(other, MoveShapesCommand):
            return False
        # Only merge if moving the exact same set of shapes
        if set(self._shape_handles) != set(other._shape_handles):
            return False

        self._shape_handle_to_final_state.update(other._shape_handle_to_final_state)
        self._is_final_states_captured = other._is_final_states_captured
        return True


class MoveNodesCommand(UndoCommand):
    """Move nodes by storing initial and final positions."""

    def __init__(
        self,
        layered_data: LayeredData,
        nodes: Iterable[VectorNode],
        node_to_initial_local_pos: dict[VectorNode, QPointF],
        text: str = 'Move Nodes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._node_handle_to_initial_local_pos: dict[int, QPointF] = {}
        self._node_handle_to_final_local_pos: dict[int, QPointF] = {}
        self._is_final_positions_captured = False

        # Resolve and cache handles once
        self._node_handles: list[int] = []
        for node in nodes:
            handle = layered_data.node_registry.get_handle(node)
            if handle is None:
                raise ValueError(f'Node {type(node).__name__} is not registered.')
            self._node_handles.append(handle)

        for node, local_pos in node_to_initial_local_pos.items():
            handle = layered_data.node_registry.get_handle(node)
            if handle is not None:
                self._node_handle_to_initial_local_pos[handle] = local_pos

    @property
    def has_changes(self) -> bool:
        for handle in self._node_handles:
            initial_local_pos = self._node_handle_to_initial_local_pos.get(handle)
            node = self._layered_data.node_registry.resolve(handle)
            if node and initial_local_pos != node.local_pos:
                return True
        return False

    def redo(self) -> None:
        if not self._is_final_positions_captured:
            for handle in self._node_handles:
                node = self._layered_data.node_registry.resolve(handle)
                if node:
                    self._node_handle_to_final_local_pos[handle] = node.local_pos
            self._is_final_positions_captured = True
            return  # Skip apply on first redo

        self._apply_positions(self._node_handle_to_final_local_pos)

    def undo(self) -> None:
        self._apply_positions(self._node_handle_to_initial_local_pos)

    def _apply_positions(self, positions: dict[int, QPointF]) -> None:
        """Apply given positions to all tracked nodes."""
        for handle, local_pos in positions.items():
            node = self._layered_data.node_registry.resolve(handle)
            if node is None:
                raise RuntimeError(f'Node handle {handle} no longer exists.')
            node.local_pos = local_pos

    def id(self) -> int:
        return self.command_type_id()

    def mergeWith(self, other: UndoCommand) -> bool:
        if not isinstance(other, MoveNodesCommand):
            return False

        # Order-agnostic comparison for robust merging
        if set(self._node_handles) != set(other._node_handles):
            return False

        self._node_handle_to_final_local_pos.update(other._node_handle_to_final_local_pos)
        self._is_final_positions_captured = other._is_final_positions_captured
        return True


class InsertNodeCommand(UndoCommand):
    """Inserts a node into any NodeBasedShape. Appends if index is None."""

    def __init__(
            self,
            layered_data: LayeredData,
            shape: NodeBasedShape,
            pos: QPointF,
            index: int | None = None,
            text: str | None = None,
            parent: UndoCommand | None = None,
    ):
        # Dynamic fallback text if not explicitly provided
        default_text = f'Insert Node into {type(shape).__name__}'
        super().__init__(text or default_text, parent)

        self._layered_data = layered_data
        self._pos = QPointF(pos)
        self._index = index

        # Convert reference to handle immediately. Fail-fast if unregistered.
        self._shape_handle = layered_data.shape_registry.get_handle(shape)
        if self._shape_handle is None:
            raise ValueError('Shape is not registered. Commands can only operate on tracked objects.')

        self._node_handle: int | None = None  # Handle is constant across undo/redo

    def redo(self) -> None:
        shape = self._layered_data.shape_registry.resolve(self._shape_handle)
        if shape is None:
            raise RuntimeError('Parent shape no longer exists. Cannot execute command.')
        if not isinstance(shape, NodeBasedShape):
            raise TypeError(f'Expected NodeBasedShape, got {type(shape).__name__}')

        # Create node at index (None = append). Signal auto-registers with temp handle.
        node = shape.create_node(self._pos, self._index)

        # First run: adopts temp handle. Subsequent redos: reclaims saved handle.
        self._node_handle = self._layered_data.node_registry.register(node, self._node_handle)

    def undo(self) -> None:
        shape = self._layered_data.shape_registry.resolve(self._shape_handle)
        if shape is None:
            return  # Safe no-op if shape was already removed
        if not isinstance(shape, NodeBasedShape):
            raise RuntimeError(f'Expected NodeBasedShape, got {type(shape).__name__}')

        node = self._layered_data.node_registry.resolve(self._node_handle)
        if node is not None:
            shape.remove_node(node)


class ShapeEntry(NamedTuple):
    shape: VectorShape
    vector: Vector
    index: int
    handle: int
    node_handles: list[int]


class RemoveShapesCommand(UndoCommand):
    """Removes shapes from their vectors without destroying them. Undo restores them."""

    def __init__(
        self,
        layered_data: LayeredData,
        shapes: Iterable[VectorShape],
        text: str = 'Remove Shapes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._shape_entries: list[ShapeEntry] = []

        for shape in shapes:
            parent = shape.parent()
            if not isinstance(parent, Vector):
                raise ValueError(f'Expected Vector parent, got {type(parent).__name__}')

            handle = layered_data.shape_registry.get_handle(shape)

            if isinstance(shape, NodeBasedShape):
                node_handles = [layered_data.node_registry.get_handle(n) for n in shape.nodes]
            else:
                node_handles = []

            self._shape_entries.append(ShapeEntry(
                shape=shape,
                vector=parent,  # Store vectors of shapes for undo (shape.parent() becomes None after removal)
                index=parent.shapes.index(shape),  # Store original indices of shapes in vector
                handle=handle,
                node_handles=node_handles,
            ))

    def redo(self) -> None:
        for shape_entry in self._shape_entries:
            shape_entry.vector.remove_shape(shape_entry.shape)

    def undo(self) -> None:
        # Restore in ascending index order to prevent insertion collisions
        for shape_entry in sorted(self._shape_entries, key=lambda e: e.index):
            shape_entry.vector.insert_shape(shape_entry.shape, shape_entry.index)
            self._layered_data.shape_registry.register(shape_entry.shape, shape_entry.handle)

            if isinstance(shape_entry.shape, NodeBasedShape):
                for node, node_handle in zip(shape_entry.shape.nodes, shape_entry.node_handles):
                    self._layered_data.node_registry.register(node, node_handle)


class NodeEntry(NamedTuple):
    handle: int
    local_pos: QPointF
    index: int


class DeleteNodesCommand(UndoCommand):
    """Permanently deletes nodes and recreates them on undo."""

    def __init__(
        self,
        layered_data: LayeredData,
        nodes: Iterable[VectorNode],
        text: str = 'Delete Nodes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data

        shape_handle_to_node_entries: dict[int, list[NodeEntry]] = defaultdict(list)

        for node in nodes:
            shape = node.parent_shape
            shape_handle = layered_data.shape_registry.get_handle(shape)
            node_handle = layered_data.node_registry.get_handle(node)
            if shape_handle is None or node_handle is None:
                raise ValueError('Shape or node not registered')

            shape_handle_to_node_entries[shape_handle].append(NodeEntry(
                handle=node_handle,
                local_pos=node.local_pos,
                index=shape.nodes.index(node),
            ))

        # Sort within each shape by descending index
        self._shape_handle_to_node_entries = {
            shape_handle: sorted(node_entries, key=lambda e: e.index, reverse=True)
            for shape_handle, node_entries in shape_handle_to_node_entries.items()
        }

    def redo(self) -> None:
        for shape_handle, node_entries in self._shape_handle_to_node_entries.items():
            shape = self._layered_data.shape_registry.resolve(shape_handle)
            assert isinstance(shape, NodeBasedShape)
            for node_entry in node_entries:
                node = self._layered_data.node_registry.resolve(node_entry.handle)
                assert node is not None
                shape.remove_node(node)

    def undo(self) -> None:
        for shape_handle, node_entries in self._shape_handle_to_node_entries.items():
            shape = self._layered_data.shape_registry.resolve(shape_handle)
            assert isinstance(shape, NodeBasedShape)
            # Reverse to restore in ascending index order
            for node_entry in reversed(node_entries):
                new_node = shape.create_node_local(node_entry.local_pos, node_entry.index)
                self._layered_data.node_registry.register(new_node, node_entry.handle)
