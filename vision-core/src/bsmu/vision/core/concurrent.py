from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from typing import Callable, Any
    from concurrent.futures import Future


class ExtendedFuture(QObject):
    _async_finished = Signal(object, object)  # Signal(callback: Callable, result: Tuple | Any)

    def __init__(self, future: Future):
        super().__init__()

        self._future = future

        # Use this signal to call slot in the thread, where class instance was created
        # (most often this is the main thread)
        self._async_finished.connect(self._call_async_callback_in_instance_thread)

    def __getattr__(self, name):
        return getattr(self._future, name)

    def add_done_unpacked_callback(self, callback: Callable):
        """Attaches a callable that will be called when the future finishes.

        :param callback: A callable that will be called when the future completes or is cancelled.
        Callable will be called with the same arguments as those returned
        from the running asynchronous function or method.
        Callable will always be called in the same thread, where ExtendedFuture instance was created.
        If the future has already completed or been cancelled then the callable will be called as soon,
        as control returns to the event loop of this ExtendedFuture instance thread.
        These callables are called in undefined order.
        """
        self._future.add_done_callback(partial(self._async_callback_with_future, callback))

    def _async_callback_with_future(self, callback: Callable, future: Future):
        """
        The callback added with concurrent.futures.Future.add_done_callback
        most often will be called in the async thread (where async method runs).
        But we want to call the |callback| in the thread, where ExtendedFuture instance was created.
        So we use Qt signal to do it.
        See https://doc.qt.io/qt-6/threads-qobject.html#signals-and-slots-across-threads
        """
        result = future.result()
        self._async_finished.emit(callback, result)

    @staticmethod
    def _call_async_callback_in_instance_thread(callback: Callable, result: tuple | Any):
        if type(result) is tuple:
            callback(*result)
        else:
            callback(result)


class ThreadPool(QObject):
    _instance = None

    def __init__(self, max_workers=None):
        super().__init__()

        self._executor = ThreadPoolExecutor(max_workers)

    @property
    def executor(self) -> ThreadPoolExecutor:
        return self._executor

    @classmethod
    def init_executor(cls, max_workers=None):
        if cls._instance:
            cls._instance.executor.shutdown()

        cls._instance = cls(max_workers)

    @classmethod
    def call_async_with_callback(cls, fn: Callable, /, *fn_args, **fn_kwargs) -> ExtendedFuture:
        assert cls._instance, 'You must first call the |init_executor| method once'

        future = cls._instance.executor.submit(fn, *fn_args, **fn_kwargs)
        extended_future = ExtendedFuture(future)
        return extended_future
