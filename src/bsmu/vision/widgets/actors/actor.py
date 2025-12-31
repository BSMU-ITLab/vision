from __future__ import annotations

from typing import Generic, TypeVar

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGraphicsItem

ModelT = TypeVar('ModelT', bound=QObject)
ItemT = TypeVar('ItemT', bound=QGraphicsItem)


class GraphicsActor(QObject, Generic[ModelT, ItemT]):
    model_about_to_change = Signal(QObject, QObject)
    model_changed = Signal(QObject)

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
        if self._model == value:
            return

        self.model_about_to_change.emit(self._model, value)
        self._model_about_to_change(value)

        self._model = value

        self._model_changed()
        self.model_changed.emit(self._model)

        self._update_graphics_item()

    @property
    def graphics_item(self) -> ItemT | None:
        return self._graphics_item

    def _create_graphics_item(self) -> ItemT:
        raise NotImplementedError(f'{self.__class__.__name__} must implement _create_graphics_item()')

    def _model_about_to_change(self, new_model: ModelT | None) -> None:
        pass

    def _model_changed(self) -> None:
        pass

    def _update_graphics_item(self) -> None:
        """Override to update graphics_item based on model state."""
        pass
