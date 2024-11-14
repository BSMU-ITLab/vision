from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from bsmu.vision.plugins.readers.manager import FileReadingManagerPlugin, FileReadingManager


class DataStoragePlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_reading_manager_plugin': 'bsmu.vision.plugins.readers.manager.FileReadingManagerPlugin',
    }

    def __init__(self, file_reading_manager_plugin: FileReadingManagerPlugin):
        super().__init__()

        self._file_reading_manager_plugin = file_reading_manager_plugin
        self._file_reading_manager: FileReadingManager | None = None

        self._data_storage: DataStorage | None = None

    def _enable(self):
        self._file_reading_manager = self._file_reading_manager_plugin.file_reading_manager

        self._data_storage = DataStorage()

        self._file_reading_manager.file_read.connect(self._data_storage.add_data)

    def _disable(self):
        self._file_reading_manager.file_read.disconnect(self._data_storage.add_data)

        self._data_storage = None


class DataStorage(QObject):  # TODO: use ItemStorage as base class
    data_added = Signal(Data)

    def __init__(self):
        super().__init__()

        self._data_array = []

    def add_data(self, data: Data):
        self._data_array.append(data)
        print('Storage data:', self._data_array)
        self.data_added.emit(data)
