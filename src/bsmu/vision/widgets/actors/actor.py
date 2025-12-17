from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from PySide6.QtWidgets import QGraphicsItem

ModelT = TypeVar('ModelT', bound=QObject)
ItemT = TypeVar('ItemT', bound=QGraphicsItem)


class GraphicsActor(Generic[ModelT, ItemT], QObject):
    def __init__(self, model: ModelT | None = None, parent: QObject | None = None):
        super().__init__(parent)

        self._model: ModelT | None = model
        self._graphics_item: ItemT | None = None

    @property
    def model(self) -> ModelT | None:
        return self._model

    @property
    def graphics_item(self) -> ItemT | None:
        return self._graphics_item
