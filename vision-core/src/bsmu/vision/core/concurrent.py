from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QThreadPool

from bsmu.vision.core.task import Task, FnTask

if TYPE_CHECKING:
    from typing import Callable, Any


class ThreadPool(QObject):
    _instance = None

    _task_to_finished_callback = {}

    def __init__(self, max_general_thread_count: int = None, max_dnn_thread_count: int = 1):
        """
        Initializes a ThreadPool object with two thread pools: one for general tasks and one for DNN tasks.
        DNN tasks use different thread pool,
        because the number of simultaneously running neural networks are very limited.
        For general tasks (e.g. input/output or calculations) we can use more threads.
        """
        super().__init__()

        max_dnn_thread_count = max(max_dnn_thread_count, 0)

        self._general_thread_pool = QThreadPool(self)
        if max_general_thread_count is None:
            max_general_thread_count = QThread.idealThreadCount() - max_dnn_thread_count
        self._general_thread_pool.setMaxThreadCount(max(max_general_thread_count, 1))

        if max_dnn_thread_count > 0:
            self._dnn_thread_pool = QThreadPool(self)
            self._dnn_thread_pool.setMaxThreadCount(max_dnn_thread_count)
        else:
            self._dnn_thread_pool = None
        logging.info(f'ThreadPool: '
                     f'general threads: {self._general_thread_pool.maxThreadCount()} / '
                     f'DNN threads: '
                     f'{self._dnn_thread_pool.maxThreadCount() if self._dnn_thread_pool is not None else 0}')

    @property
    def general_thread_pool(self) -> QThreadPool:
        return self._general_thread_pool

    @property
    def dnn_thread_pool(self) -> QThreadPool | None:
        return self._dnn_thread_pool

    @classmethod
    def create_instance(cls, max_general_thread_count: int = None, max_dnn_thread_count: int = 1):
        cls._instance = cls(max_general_thread_count, max_dnn_thread_count)

    @classmethod
    def call_async(cls, fn: Callable, /, *fn_args, **fn_kwargs) -> Task:
        """
        :param fn: is positional-only parameter,
        because it allows to pass into fn_kwargs keyword argument named as fn.
        """
        task = cls.fn_task(fn, *fn_args, **fn_kwargs)
        cls.run_async_task(task)
        return task

    @classmethod
    def call_async_dnn(cls, fn: Callable, /, *fn_args, **fn_kwargs) -> Task:
        task = cls.fn_task(fn, *fn_args, **fn_kwargs)
        cls.run_async_dnn_task(task)
        return task

    @staticmethod
    def fn_task(fn: Callable, /, *fn_args, **fn_kwargs) -> Task:
        return FnTask(fn, *fn_args, **fn_kwargs)

    @classmethod
    def run_async_task(cls, task: Task, dnn: bool = False):
        # We have to process task finished callback in the ThreadPool (not in the Task class),
        # because else task will be deleted by ThreadPool when the task exits the run function.
        # In the current approach, the task is not deleted until `_on_task_finished` is executed.
        task_finished_callback = partial(cls._on_task_finished, task)
        cls._task_to_finished_callback[task] = task_finished_callback
        task.finished.connect(task_finished_callback)

        assert cls._instance, 'You must first call the `create_instance` method once'
        if dnn and cls._instance.dnn_thread_pool is not None:
            cls._instance.dnn_thread_pool.start(task)
        else:
            cls._instance.general_thread_pool.start(task)

    @classmethod
    def run_async_dnn_task(cls, task: Task):
        cls.run_async_task(task, dnn=True)

    @classmethod
    def _on_task_finished(cls, task: Task, result: tuple | Any):
        task.finished.disconnect(cls._task_to_finished_callback[task])
        del cls._task_to_finished_callback[task]

        task.call_finished_callback()
