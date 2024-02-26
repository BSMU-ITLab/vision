from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.storages import ItemStorage

if TYPE_CHECKING:
    from typing import Any
    from bsmu.vision.core.task import Task


class TaskStoragePlugin(Plugin):
    def __init__(self):
        super().__init__()

        self._task_storage: TaskStorage | None = None

    @property
    def task_storage(self) -> TaskStorage:
        return self._task_storage

    def _enable(self):
        self._task_storage = TaskStorage()

    def _disable(self):
        self._task_storage = None


class TaskStorage(ItemStorage):
    def __init__(self, finished_task_removing_delay_msec: int = 2000):
        super().__init__()

        self._finished_task_removing_delay_msec = finished_task_removing_delay_msec

    def _after_add_item(self, item: Task, index: int):
        # Use single shot connection to disconnect automatically.
        # Maybe we should use `type=Qt.AutoConnection | Qt.SingleShotConnection`,
        # but in PySide 6.5.2 it throws the error:
        # TypeError: unsupported operand type(s) for |: 'ConnectionType' and 'ConnectionType'
        item.finished.connect(
            partial(self._on_task_finished, item, index), type=Qt.SingleShotConnection)

    def _on_task_finished(self, task: Task, index: int, result: tuple | Any):
        # Remove task from the storage with delay
        QTimer.singleShot(self._finished_task_removing_delay_msec, partial(self._remove_item, task, index))
