from __future__ import annotations

from typing import Generic, TypeVar

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QGraphicsItem

ModelT = TypeVar('ModelT', bound=QObject)
ItemT = TypeVar('ItemT', bound=QGraphicsItem)


class GraphicsActor(Generic[ModelT, ItemT], QObject):
    def __init__(self, model: ModelT | None = None, parent: QObject | None = None):
        super().__init__(parent)

        self._model: ModelT | None = None
        self._graphics_item: ItemT | None = self._create_graphics_item()

        if model is not None:
            self.model = model

    @property
    def model(self) -> ModelT | None:
        return self._model

    @model.setter
    def model(self, value: ModelT | None) -> None:
        if self._model is not None:
            self._disconnect_model_signals()

        self._model = value

        if self._model is not None:
            self._connect_model_signals()

        # Refresh visual
        self._update_visual()

    @property
    def graphics_item(self) -> ItemT | None:
        return self._graphics_item

    def _create_graphics_item(self) -> ItemT:
        raise NotImplementedError(f'{self.__class__.__name__} must implement _create_graphics_item()')

    def _connect_model_signals(self) -> None:
        """Override to connect model signals (e.g., model.changed)."""
        pass

    def _disconnect_model_signals(self) -> None:
        """Override to disconnect model signals."""
        pass

    def _update_visual(self) -> None:
        """Override to update graphics_item based on model state."""
        pass
