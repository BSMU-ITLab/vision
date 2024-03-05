from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QThreadPool

from bsmu.vision.core.task import Task, FnTask, DnnFnTask

if TYPE_CHECKING:
    from typing import Callable, Any, Type


class ThreadPool(QObject):
    _instance = None

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

        # Keep references on running tasks, while they are not finished
        # to prevent them from being deleted by the garbage collector
        self._running_tasks = set()

        self._task_to_task_finished_handler: dict[Task, Callable] = {}

    @property
    def general_thread_pool(self) -> QThreadPool:
        return self._general_thread_pool

    @property
    def dnn_thread_pool(self) -> QThreadPool | None:
        return self._dnn_thread_pool

    @property
    def running_tasks(self) -> set[Task]:
        return self._running_tasks

    @property
    def task_to_task_finished_handler(self) -> dict[Task, Callable]:
        return self._task_to_task_finished_handler

    @classmethod
    def create_instance(cls, max_general_thread_count: int = None, max_dnn_thread_count: int = 1):
        cls._instance = cls(max_general_thread_count, max_dnn_thread_count)

    @classmethod
    def call_async(cls, fn: Callable, /, *fn_args, **fn_kwargs) -> Task:
        """
        Do not use this method, if you are going to use task.finished or other signals,
        because task can be finished earlier (and signal emitted too), before this method returns the task and
        signals will be connected. For such cases you have to create a Task instance themself,
        connect to task.finished (or other) signals and then use run_async_task method.

        :param fn: is positional-only parameter,
        because it allows to pass into fn_kwargs keyword argument named as fn.
        """
        return cls._call_async_using_task_type(FnTask, fn, *fn_args, **fn_kwargs)

    @classmethod
    def call_async_dnn(cls, fn: Callable, /, *fn_args, **fn_kwargs) -> Task:
        return cls._call_async_using_task_type(DnnFnTask, fn, *fn_args, **fn_kwargs)

    @classmethod
    def _call_async_using_task_type(cls, task_type: Type[FnTask], fn: Callable, /, *fn_args, **fn_kwargs) -> FnTask:
        task = task_type(fn, fn.__name__)
        cls.run_async_task_with_args(task, *fn_args, **fn_kwargs)
        return task

    @classmethod
    def run_async_task_with_args(cls, task: FnTask, /, *fn_args, **fn_kwargs):
        task.set_fn_args(*fn_args, **fn_kwargs)
        cls.run_async_task(task)

    @classmethod
    def run_async_task(cls, task: Task):
        assert cls._instance, 'You must first call the `create_instance` method once'

        task_finished_handler = partial(cls._on_task_finished, task)
        cls._instance.task_to_task_finished_handler[task] = task_finished_handler
        task.finished.connect(task_finished_handler)

        # Set autoDelete to False, to prevent task from being deleted by QThreadPool, after the Task.run() returns.
        # If task will be deleted, we will not be able to display it's status e.g.
        task.setAutoDelete(False)
        # TODO: PySide 6.6.2 leads to memory leak, when autoDelete is False
        #  see: https://bugreports.qt.io/browse/PYSIDE-2621
        #  see: https://stackoverflow.com/questions/78076185/qrunnable-with-setautodeletefalse-leads-to-memory-leak-in-pyside6

        cls._instance.running_tasks.add(task)

        if task.uses_dnn and cls._instance.dnn_thread_pool is not None:
            cls._instance.dnn_thread_pool.start(task)
        else:
            cls._instance.general_thread_pool.start(task)

    @classmethod
    def _on_task_finished(cls, task: Task, result: tuple | Any):
        cls._instance.running_tasks.remove(task)

        task_finished_handler = cls._instance.task_to_task_finished_handler.pop(task)
        task.finished.disconnect(task_finished_handler)
