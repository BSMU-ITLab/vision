from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.models import positive_list_insert_index, positive_list_remove_index


class ItemStorage(QObject):
    item_adding = Signal(object, int)
    item_added = Signal(object, int)
    item_removing = Signal(object, int)
    item_removed = Signal(object, int)

    def __init__(self):
        super().__init__()

        self._items = []

    @property
    def items(self) -> list:
        return self._items

    def add_item(self, item, index: int | None = None):
        """
        :param item: item to add
        :param index: if is None then add item to the end
        """
        index = positive_list_insert_index(self._items, index)
        self.item_adding.emit(item, index)
        self._before_add_item(item, index)
        self._items.insert(index, item)
        self._after_add_item(item, index)
        self.item_added.emit(item, index)

    def remove_item(self, item):
        self._remove_item(item, self._items.index(item))

    def remove_item_by_index(self, index: int = None):
        """
        :param index: if is None then remove last item
        """
        index = positive_list_remove_index(self._items, index)
        item = self._items[index]
        self._remove_item(item, index)

    def _remove_item(self, item, index: int):
        self.item_removing.emit(item, index)
        self._before_remove_item(item, index)
        self._items.pop(index)
        self._after_remove_item(item, index)
        self.item_removed.emit(item, index)

    def _before_add_item(self, item, index: int):
        # Override this method in subclasses to provide additional logic before adding an item
        pass

    def _after_add_item(self, item, index: int):
        # Override this method in subclasses to provide additional logic after adding an item
        pass

    def _before_remove_item(self, item, index: int):
        # Override this method in subclasses to provide additional logic before removing an item
        pass

    def _after_remove_item(self, item, index: int):
        # Override this method in subclasses to provide additional logic after removing an item
        pass

    def print_items(self):
        for item in self._items:
            print(item)
