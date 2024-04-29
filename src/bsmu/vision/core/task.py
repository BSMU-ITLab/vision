from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QRunnable

if TYPE_CHECKING:
    from typing import Callable, Any


class TaskSignals(QObject):
    finished = Signal(object, arguments=['result'])  # result: tuple | Any
    progress_changed = Signal(float, arguments=['value'])
    callback_call_requested = Signal()


class Task(QRunnable):
    def __init__(self, name: str = '', uses_dnn: bool = False):
        super().__init__()

        self._name = name
        self._uses_dnn = uses_dnn

        self._progress = -1  # as a percentage [0; 100]. Negative value indicate, that progress is undefined
        self._signals = TaskSignals()
        # Use the next signal connection to call the slot in this constructor thread (not in Task.run() thread)
        # This is being implemented by Qt.QueuedConnection
        # See: https://doc.qt.io/qt-6/threads-qobject.html#signals-and-slots-across-threads
        self._signals.callback_call_requested.connect(self._call_finished_callback_in_constructor_thread)

        self._result: tuple | Any = None
        self._is_finished: bool = False
        self._on_finished: Callable | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def uses_dnn(self) -> bool:
        return self._uses_dnn

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
            self._call_finished_callback()

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
        self._emit_signal_to_call_finished_callback_in_constructor_thread()

    def _run(self) -> tuple | Any:
        pass

    def _emit_signal_to_call_finished_callback_in_constructor_thread(self):
        self._signals.callback_call_requested.emit()

    def _call_finished_callback_in_constructor_thread(self):
        self._call_finished_callback()
        # Emit `finished` signal only after the callback, to be sure,
        # that ThreadPool is still keeping the task reference, while callback is running
        # TODO: can the task reference be deleted by ThreadPool, if in the callback will be created one more thread?
        self.finished.emit(self._result)

    def _call_finished_callback(self):
        if self._on_finished is None:
            return

        if type(self._result) is tuple:
            self._on_finished(*self._result)
        else:
            self._on_finished(self._result)

        # To prevent double calling of the callback
        self._on_finished = None

    def _change_step_progress(self, finished_step_count: int, total_step_count: int):
        self.progress = finished_step_count / total_step_count * 100

    def _change_subtask_based_progress(
            self, finished_subtask_count: int, total_subtask_count: int, current_subtask_progress: float):
        self.progress = (finished_subtask_count * 100 + current_subtask_progress) / total_subtask_count


class DnnTask(Task):
    def __init__(self, name: str = ''):
        super().__init__(name, uses_dnn=True)


class FnTask(Task):
    def __init__(self, fn: Callable, name: str = '', uses_dnn: bool = False):
        super().__init__(name, uses_dnn)

        self._fn = fn
        self._fn_args = ()
        self._fn_kwargs = {}

    def set_fn_args(self, *fn_args, **fn_kwargs):
        self._fn_args = fn_args
        self._fn_kwargs = fn_kwargs

    def _run(self) -> tuple | Any:
        return self._fn(*self._fn_args, **self._fn_kwargs)


class DnnFnTask(FnTask):
    def __init__(self, fn: Callable, name: str = ''):
        super().__init__(fn, name, uses_dnn=True)
