from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple, TypeVar, Generic, TYPE_CHECKING

from PySide6.QtCore import QPointF

from bsmu.vision.core.data.vector import Vector
from bsmu.vision.core.data.vector.shapes import NodeBasedShape
from bsmu.vision.undo import UndoCommand

if TYPE_CHECKING:
    from typing import Iterable, Sequence

    from bsmu.vision.core.data.layered import LayeredData
    from bsmu.vision.core.data.vector.shapes import VectorNode, VectorShape

NodeBasedShapeT = TypeVar('NodeBasedShapeT', bound=NodeBasedShape)


class CreateNodeBasedShapeCommand(UndoCommand, Generic[NodeBasedShapeT]):
    """Generic command to create any NodeBasedShape."""

    def __init__(
            self,
            layered_data: LayeredData,
            vector: Vector,
            shape_class: type[NodeBasedShapeT],
            points: Sequence[QPointF],
            origin: QPointF | None = None,
            text: str | None = None,
            parent: UndoCommand | None = None,
    ):
        default_text = f'Create {shape_class.__name__}'
        super().__init__(text or default_text, parent)

        self._layered_data = layered_data
        self._vector = vector
        self._shape_class = shape_class
        self._points = points
        self._origin = origin

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
            self._shape = self._shape_class(self._points, self._origin)

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
    """Move shapes by changing their origin transform."""

    def __init__(
        self,
        layered_data: LayeredData,
        shapes: Iterable[VectorShape],
        offset: QPointF,
        text: str = 'Move Shapes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._offset = QPointF(offset)

        # Validate and collect handles
        handles: list[int] = []
        for shape in shapes:
            handle = layered_data.shape_registry.get_handle(shape)
            if handle is None:
                raise ValueError(
                    f'Shape {type(shape).__name__} is not registered. '
                    f'Commands can only operate on tracked objects.'
                )
            handles.append(handle)
        self._shape_handles: frozenset[int] = frozenset(handles)

        self._shape_handle_to_initial_origin: dict[int, QPointF] | None = None

    def redo(self) -> None:
        if self._shape_handle_to_initial_origin is None:
            self._shape_handle_to_initial_origin = {}
            for handle in self._shape_handles:
                shape = self._layered_data.shape_registry.resolve(handle)
                if shape is None:
                    raise RuntimeError(f'Shape handle {handle} no longer exists. Command cannot execute.')
                self._shape_handle_to_initial_origin[handle] = shape.origin

        for handle in self._shape_handles:
            shape = self._layered_data.shape_registry.resolve(handle)
            if shape is not None:
                shape.move_by(self._offset)

    def undo(self) -> None:
        assert self._shape_handle_to_initial_origin is not None, 'Command must be executed before undo.'
        for handle, initial_origin in self._shape_handle_to_initial_origin.items():
            shape = self._layered_data.shape_registry.resolve(handle)
            if shape is not None:
                shape.origin = initial_origin

    def id(self) -> int:
        return self.command_type_id()

    def mergeWith(self, other: UndoCommand) -> bool:
        if not isinstance(other, MoveShapesCommand):
            return False
        # Only merge if moving the exact same set of shapes
        if self._shape_handles != other._shape_handles:
            return False

        # Merge offsets
        self._offset += other._offset
        return True


class MoveNodesCommand(UndoCommand):
    """Move individual nodes by a delta offset."""

    def __init__(
        self,
        layered_data: LayeredData,
        nodes: Iterable[VectorNode],
        offset: QPointF,
        text: str = 'Move Nodes',
        parent: UndoCommand | None = None,
    ):
        super().__init__(text, parent)

        self._layered_data = layered_data
        self._offset = QPointF(offset)

        # Validate and collect handles
        handles: list[int] = []
        for node in nodes:
            handle = layered_data.node_registry.get_handle(node)
            if handle is None:
                raise ValueError(
                    f'Node {type(node).__name__} is not registered. '
                    f'Commands can only operate on tracked objects.'
                )
            handles.append(handle)
        self._node_handles: frozenset[int] = frozenset(handles)

        self._node_handle_to_initial_local_pos: dict[int, QPointF] | None = None

    def redo(self) -> None:
        if self._node_handle_to_initial_local_pos is None:
            self._node_handle_to_initial_local_pos = {}
            for handle in self._node_handles:
                node = self._layered_data.node_registry.resolve(handle)
                if node is None:
                    raise RuntimeError(f'Node handle {handle} no longer exists. Command cannot execute.')
                self._node_handle_to_initial_local_pos[handle] = node.local_pos

        for handle in self._node_handles:
            node = self._layered_data.node_registry.resolve(handle)
            if node is not None:
                node.move_by(self._offset)

    def undo(self) -> None:
        assert self._node_handle_to_initial_local_pos is not None, 'Command must be executed before undo.'
        for handle, initial_local_pos in self._node_handle_to_initial_local_pos.items():
            node = self._layered_data.node_registry.resolve(handle)
            if node is not None:
                node.local_pos = initial_local_pos

    def id(self) -> int:
        return self.command_type_id()

    def mergeWith(self, other: UndoCommand) -> bool:
        if not isinstance(other, MoveNodesCommand):
            return False
        if self._node_handles != other._node_handles:
            return False

        self._offset += other._offset
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
