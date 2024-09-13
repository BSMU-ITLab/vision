from __future__ import annotations

from typing import TYPE_CHECKING, List, Any

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QDockWidget, QTableView

from bsmu.vision.core.models.table import RecordTableModel, TableColumn
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.task import Task
from bsmu.vision.widgets.delegates.progress_delegate import ProgressDelegate

if TYPE_CHECKING:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QWidget

    from bsmu.vision.plugins.windows.main import MainWindowPlugin, MainWindow
    from bsmu.vision.plugins.storages.task_storage import TaskStorage, TaskStoragePlugin


class TaskStorageViewPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
    }

    def __init__(self, main_window_plugin: MainWindowPlugin, task_storage_plugin: TaskStoragePlugin):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._task_storage_plugin = task_storage_plugin

        self._task_storage_table_view: TaskStorageTableView | None = None
        self._task_storage_table_view_dock_widget: QDockWidget | None = None

        self._task_storage_table_model: TaskStorageTableModel | None = None
        self._progress_delegate: ProgressDelegate | None = None

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window

        task_storage = self._task_storage_plugin.task_storage
        self._task_storage_table_model = TaskStorageTableModel(task_storage)

        self._task_storage_table_view = TaskStorageTableView()
        self._task_storage_table_view.setModel(self._task_storage_table_model)
        self._task_storage_table_view_dock_widget = QDockWidget('Tasks', self._main_window)
        self._task_storage_table_view_dock_widget.setWidget(self._task_storage_table_view)

        self._progress_delegate = ProgressDelegate(parent=self._task_storage_table_view)
        progress_column_number = self._task_storage_table_model.column_number(NameProgressTableColumn)
        self._task_storage_table_view.setItemDelegateForColumn(progress_column_number, self._progress_delegate)

        self._main_window.addDockWidget(Qt.RightDockWidgetArea, self._task_storage_table_view_dock_widget)

    def _disable(self):
        self._main_window.removeDockWidget(self._task_storage_table_view_dock_widget)

        self._progress_delegate = None

        self._task_storage_table_view_dock_widget = None
        self._task_storage_table_view = None

        self._task_storage_table_model = None

        self._main_window = None


class NameProgressTableColumn(TableColumn):
    TITLE = 'Name / Progress'


class TaskStorageTableModel(RecordTableModel):
    def __init__(self, record_storage: TaskStorage, parent: QObject = None):
        super().__init__(record_storage, Task, [NameProgressTableColumn], parent)

    @property
    def storage_records(self) -> List[Task]:
        return self.record_storage.items

    def _record_data(self, record: Task, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole:
            if index.column() == self.column_number(NameProgressTableColumn):
                return record

    def _on_record_storage_changing(self):
        self.record_storage.item_adding.disconnect(self._on_storage_record_adding)
        self.record_storage.item_added.disconnect(self._on_storage_record_added)
        self.record_storage.item_removing.disconnect(self._on_storage_record_removing)
        self.record_storage.item_removed.disconnect(self._on_storage_record_removed)

    def _on_record_storage_changed(self):
        self.record_storage.item_adding.connect(self._on_storage_record_adding)
        self.record_storage.item_added.connect(self._on_storage_record_added)
        self.record_storage.item_removing.connect(self._on_storage_record_removing)
        self.record_storage.item_removed.connect(self._on_storage_record_removed)

    def _on_record_added(self, record: Task, row: int):
        self._create_record_connections(
            record,
            ((record.progress_changed, self._on_task_progress_changed),
             (record.finished, self._on_task_finished),
             ))

    def _on_task_progress_changed(self, task: Task, progress: float):
        self._update_task_name_progress_column(task)

    def _on_task_finished(self, task: Task, result: tuple | Any):
        self._update_task_name_progress_column(task)

    def _update_task_name_progress_column(self, task: Task):
        name_progress_model_index = self.index(self.record_row(task), self.column_number(NameProgressTableColumn))
        self.dataChanged.emit(name_progress_model_index, name_progress_model_index)


class TaskStorageTableView(QTableView):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().hide()
