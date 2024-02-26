from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QRunnable

if TYPE_CHECKING:
    from typing import Callable, Any


class TaskSignals(QObject):
    finished = Signal(object, arguments=['result'])  # result: tuple | Any
    progress_changed = Signal(float, arguments=['value'])


class Task(QRunnable):
    def __init__(self, name: str = ''):
        super().__init__()

        self._name = name

        self._progress = -1  # as a percentage [0; 100]. Negative value indicate, that progress is undefined
        self._signals = TaskSignals()

        self._result: tuple | Any = None
        self._is_finished: bool = False
        self._on_finished: Callable | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def progress_known(self) -> bool:
        return self._progress >= 0

    @property
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float):
        if self._progress != value:
            self._progress = value
            self.progress_changed.emit(self._progress)

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    @property
    def on_finished(self) -> Callable | None:
        return self._on_finished

    @on_finished.setter
    def on_finished(self, callback: Callable):
        self._on_finished = callback
        if self._is_finished:
            self.call_finished_callback()

    @property
    def result(self) -> tuple | Any:
        return self._result

    @property
    def finished(self) -> Signal:
        return self._signals.finished

    @property
    def progress_changed(self) -> Signal:
        return self._signals.progress_changed

    def run(self):
        self._result = self._run()
        self._is_finished = True
        self.finished.emit(self._result)

    def _run(self) -> tuple | Any:
        pass

    def call_finished_callback(self):
        if self._on_finished is None:
            return

        if type(self._result) is tuple:
            self._on_finished(*self._result)
        else:
            self._on_finished(self._result)

        # To prevent double calling of the callback
        self._on_finished = None


class FnTask(Task):
    def __init__(self, fn: Callable, /, *fn_args, **fn_kwargs):
        super().__init__(fn.__name__)

        self._fn = fn
        self._fn_args = fn_args
        self._fn_kwargs = fn_kwargs

    def _run(self) -> tuple | Any:
        return self._fn(*self._fn_args, **self._fn_kwargs)
