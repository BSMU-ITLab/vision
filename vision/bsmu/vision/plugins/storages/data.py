from __future__ import annotations

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin
from bsmu.vision_core.data import Data


class DataStoragePlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        file_loading_manager_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin')
        self.file_loading_manager = file_loading_manager_plugin.file_loading_manager

        self.data_storage = DataStorage()

    def _enable(self):
        self.file_loading_manager.file_loaded.connect(self.data_storage.add_data)

    def _disable(self):
        self.file_loading_manager.file_loaded.disconnect(self.data_storage.add_data)


class DataStorage(QObject):
    data_added = Signal(Data)

    def __init__(self):
        super().__init__()

        self._data_array = []

    def add_data(self, data: Data):
        self._data_array.append(data)
        print('Storage data:', self._data_array)
        self.data_added.emit(data)
