from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.storages import ItemStorage

if TYPE_CHECKING:
    from typing import Any, Callable
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

        self._task_to_task_finished_handler = {}
        self._task_to_delayed_remove_timer_handler_pair = {}

    def _after_add_item(self, item: Task, index: int):
        # Could use Qt.SingleShotConnection, but in PySide 6.6.2 it leads to memory leak of Task
        task_finished_handler = partial(self._on_task_finished, item)
        item.finished.connect(task_finished_handler)
        self._task_to_task_finished_handler[item] = task_finished_handler

    def _before_remove_item(self, item: Task, index: int):
        task_finished_handler = self._task_to_task_finished_handler.pop(item)
        item.finished.disconnect(task_finished_handler)

        delayed_remove_timer_handler_pair = self._task_to_delayed_remove_timer_handler_pair.pop(item, None)
        # The item may have been removed before the connection was made
        if delayed_remove_timer_handler_pair is not None:
            delayed_remove_timer_handler_pair.timer.timeout.disconnect(
                delayed_remove_timer_handler_pair.timeout_handler)

    def _on_task_finished(self, task: Task, result: tuple | Any):
        """Remove task from the storage with delay"""

        # A task may have been removed before it is finished
        if task not in self._items:
            return

        # QTimer.singleShot leads to memory leak of Task in PySide 6.6.2, so do not use the next method
        # QTimer.singleShot(self._finished_task_removing_delay_msec, partial(self.try_remove_item, task))

        timer = QTimer()
        timer.setSingleShot(True)
        try_remove_task_handler = partial(self.try_remove_item, task)
        self._task_to_delayed_remove_timer_handler_pair[task] = self._TimerHandlerPair(timer, try_remove_task_handler)
        timer.timeout.connect(try_remove_task_handler)
        timer.start(self._finished_task_removing_delay_msec)

    @dataclass
    class _TimerHandlerPair:
        timer: QTimer
        timeout_handler: Callable
