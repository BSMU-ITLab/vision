from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data.vector.shapes import NodeBasedShape

if TYPE_CHECKING:
    from bsmu.vision.core.data.vector.shapes import VectorShape, VectorNode
    from bsmu.vision.core.layers import VectorLayer


class SelectionManager(QObject):
    selection_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._selected_shapes: set[VectorShape] = set()
        self._selected_nodes: set[VectorNode] = set()

        # Shapes monitored for node removal signals
        self._monitored_shapes: set[NodeBasedShape] = set()

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
        if shape not in self._selected_shapes:
            self._selected_shapes = {shape}
            self._selected_nodes.clear()
            self.selection_changed.emit()

    def select_node(self, node: VectorNode) -> None:
        if node not in self._selected_nodes:
            self._selected_nodes = {node}
            self._selected_shapes.clear()
            self.selection_changed.emit()

    def toggle_shape_selection(self, shape: VectorShape) -> None:
        if shape in self._selected_shapes:
            self._selected_shapes.remove(shape)
        else:
            self._selected_shapes.add(shape)
        self.selection_changed.emit()

    def toggle_node_selection(self, node: VectorNode) -> None:
        if node in self._selected_nodes:
            self._selected_nodes.remove(node)
        else:
            self._selected_nodes.add(node)
        self.selection_changed.emit()

    def is_shape_selected(self, shape: VectorShape) -> bool:
        return shape in self._selected_shapes

    def is_node_selected(self, node: VectorNode) -> bool:
        return node in self._selected_nodes

    def selected_shape_nodes(self, shape: VectorShape) -> set[VectorNode]:
        """Return selected nodes that belong to the given shape."""
        return {node for node in self._selected_nodes if node.parent_shape is shape}

    def deselect_shape(self, shape: VectorShape) -> None:
        if shape in self._selected_shapes:
            self._selected_shapes.remove(shape)
            self.selection_changed.emit()

    def deselect_node(self, node: VectorNode) -> None:
        if node in self._selected_nodes:
            self._selected_nodes.remove(node)
            self.selection_changed.emit()

    def observe_layer(self, layer: VectorLayer) -> None:
        """Start monitoring layer for shape and node removals."""
        layer.shape_removed.connect(self._on_layer_shape_removed)
        layer.shape_added.connect(self._on_layer_shape_added)

        for shape in layer.shapes:
            self._observe_shape(shape)

    def unobserve_layer(self, layer: VectorLayer) -> None:
        """Stop monitoring layer and clean up subscriptions."""
        layer.shape_removed.disconnect(self._on_layer_shape_removed)
        layer.shape_added.disconnect(self._on_layer_shape_added)

        for shape in list(self._monitored_shapes):
            self._unobserve_shape(shape)

    def _observe_shape(self, shape: VectorShape) -> None:
        """Monitor shape for node removal signals."""
        if isinstance(shape, NodeBasedShape) and shape not in self._monitored_shapes:
            shape.node_removed.connect(self._on_shape_node_removed)
            self._monitored_shapes.add(shape)

    def _unobserve_shape(self, shape: VectorShape) -> None:
        if shape in self._monitored_shapes:
            shape.node_removed.disconnect(self._on_shape_node_removed)
            self._monitored_shapes.remove(shape)

    def _on_layer_shape_added(self, shape: VectorShape, index: int) -> None:
        self._observe_shape(shape)

    def _on_layer_shape_removed(self, shape: VectorShape, index: int) -> None:
        """Deselect removed shape/nodes and stop monitoring."""
        changed = False

        if shape in self._selected_shapes:
            self._selected_shapes.remove(shape)
            changed = True

        # Batch deselect nodes belonging to this shape
        nodes_to_deselect = [n for n in self._selected_nodes if n.parent_shape is shape]
        if nodes_to_deselect:
            for node in nodes_to_deselect:
                self._selected_nodes.remove(node)
            changed = True

        self._unobserve_shape(shape)

        if changed:
            self.selection_changed.emit()

    def _on_shape_node_removed(self, node: VectorNode, index: int) -> None:
        self.deselect_node(node)
