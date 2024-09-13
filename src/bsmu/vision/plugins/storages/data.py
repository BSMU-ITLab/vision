from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager


class DataStoragePlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(self, file_loading_manager_plugin: FileLoadingManagerPlugin):
        super().__init__()

        self._file_loading_manager_plugin = file_loading_manager_plugin
        self._file_loading_manager: FileLoadingManager | None = None

        self._data_storage: DataStorage | None = None

    def _enable(self):
        self._file_loading_manager = self._file_loading_manager_plugin.file_loading_manager

        self._data_storage = DataStorage()

        self._file_loading_manager.file_loaded.connect(self._data_storage.add_data)

    def _disable(self):
        self._file_loading_manager.file_loaded.disconnect(self._data_storage.add_data)

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
