from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from typing import Callable
    from concurrent.futures import Future


class ThreadPool(QObject):
    _instance = None

    async_finished = Signal(object, object)  # Signal(callback: Callable, result: Tuple | Any)

    def __init__(self, max_workers=None):
        super().__init__()

        self._executor = ThreadPoolExecutor(max_workers)

        # Use this signal to call slot in the thread, where class instance was created
        # (most often this is the main thread)
        self.async_finished.connect(self._call_async_callback_in_instance_thread)

    @property
    def executor(self) -> ThreadPoolExecutor:
        return self._executor

    @classmethod
    def init_executor(cls, max_workers=None):
        if cls._instance:
            cls._instance.executor.shutdown()

        cls._instance = cls(max_workers)

    @classmethod
    def call_async_with_callback(cls, async_method: Callable, *async_method_args, callback: Callable):
        assert cls._instance, 'You must first call the |init_executor| method once'
        assert callable(callback), 'Callback has to be callable'

        future = cls._instance.executor.submit(async_method, *async_method_args)
        future.add_done_callback(
            partial(cls._instance.async_callback_with_future, callback))

    def async_callback_with_future(self, callback: Callable, future: Future):
        """
        This callback most often will be called in the async thread (where async method was called)
        But we want to call |callback| in the thread, where instance was created.
        So we use Qt signal to do it.
        See https://doc.qt.io/qt-6/threads-qobject.html#signals-and-slots-across-threads
        """
        result = future.result()
        self.async_finished.emit(callback, result)

    @staticmethod
    def _call_async_callback_in_instance_thread(callback: Callable, result):
        if type(result) is tuple:
            callback(*result)
        else:
            callback(result)
