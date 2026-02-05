from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from bsmu.vision.core.data.vector.shapes import VectorShape, VectorNode


class SelectionManager(QObject):
    selection_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._selected_shapes: set[VectorShape] = set()
        self._selected_nodes: set[VectorNode] = set()

    @property
    def selected_shapes(self) -> frozenset[VectorShape]:
        return frozenset(self._selected_shapes)

    @property
    def selected_nodes(self) -> frozenset[VectorNode]:
        return frozenset(self._selected_nodes)

    def clear_selection(self) -> None:
        if self._selected_shapes or self._selected_nodes:
            self._selected_shapes.clear()
            self._selected_nodes.clear()
            self.selection_changed.emit()

    def select_shape(self, shape: VectorShape) -> None:
        self._selected_shapes = { shape }
        self._selected_nodes.clear()
        self.selection_changed.emit()

    def select_node(self, node: VectorNode) -> None:
        self._selected_nodes = { node }
        self._selected_shapes = { node.parent_shape }
        self.selection_changed.emit()

    def toggle_shape_selection(self, shape: VectorShape) -> None:
        if shape in self._selected_shapes:
            self._selected_shapes.discard(shape)
        else:
            self._selected_shapes.add(shape)
        self.selection_changed.emit()

    def toggle_node_selection(self, node: VectorNode) -> None:
        if node in self._selected_nodes:
            self._selected_nodes.discard(node)
        else:
            self._selected_nodes.add(node)
            self._selected_shapes.add(node.parent_shape)
        # Optional: if no nodes of a shape remain selected, maybe deselect shape? (UX choice)
        self.selection_changed.emit()

    def is_shape_selected(self, shape: VectorShape) -> bool:
        return shape in self._selected_shapes

    def is_node_selected(self, node: VectorNode) -> bool:
        return node in self._selected_nodes

    def selected_shape_nodes(self, shape: VectorShape) -> set[VectorNode]:
        return { node for node in self._selected_nodes if node.parent_shape is shape }
