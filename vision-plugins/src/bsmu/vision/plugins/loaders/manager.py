from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.task import FnTask

if TYPE_CHECKING:
    from typing import Type
    from pathlib import Path

    from bsmu.vision.core.task import Task
    from bsmu.vision.plugins.loaders.base import FileLoader
    from bsmu.vision.plugins.loaders.registry import FileLoaderRegistryPlugin
    from bsmu.vision.plugins.storages import TaskStorage, TaskStoragePlugin


class FileLoadingManagerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_loader_registry_plugin': 'bsmu.vision.plugins.loaders.registry.FileLoaderRegistryPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
    }

    def __init__(self, file_loader_registry_plugin: FileLoaderRegistryPlugin, task_storage_plugin: TaskStoragePlugin):
        super().__init__()

        self._file_loader_registry_plugin = file_loader_registry_plugin
        self._task_storage_plugin = task_storage_plugin

        self._file_loading_manager: FileLoadingManager | None = None

    @property
    def file_loading_manager(self) -> FileLoadingManager:
        return self._file_loading_manager

    def _enable(self):
        self._file_loading_manager = FileLoadingManager(
            self._file_loader_registry_plugin.processor_registry, self._task_storage_plugin.task_storage)

    def _disable(self):
        self._file_loading_manager = None


class FileLoadingManager(QObject):
    file_loaded = Signal(Data)

    def __init__(self, file_loader_registry: FileLoaderRegistry, task_storage: TaskStorage | None = None):
        super().__init__()

        self.file_loader_registry = file_loader_registry
        self._task_storage = task_storage

    def can_load_file(self, path: Path) -> bool:
        return self._loader_cls(path) is not None

    def load_file(self, path: Path, **kwargs) -> Data | None:
        logging.info(f'Load file: {path}')
        data = None
        if path.exists():
            format_loader_cls = self._loader_cls(path)
            if format_loader_cls is not None:
                format_loader = format_loader_cls()
                data = format_loader.load_file(path, **kwargs)
            else:
                logging.info(f'Cannot load the {path} file, because suitable loader is not found')
        else:
            logging.info(f'Cannot load the {path} file, because it is not exist')
        self.file_loaded.emit(data)
        return data

    def load_file_async(self, path: Path, **kwargs) -> Task:
        return ThreadPool.call_async(
            self.load_file,
            path,
            **kwargs,
        )

    def load_file_async_and_add_task_into_task_storage(self, path: Path, **kwargs) -> Task:
        file_loading_task = FnTask(self.load_file, f'File Loading: {path.name}')
        if self._task_storage is not None:
            self._task_storage.add_item(file_loading_task)
        ThreadPool.run_async_task_with_args(file_loading_task, path, **kwargs)
        return file_loading_task

    def _loader_cls(self, path: Path) -> Type[FileLoader] | None:
        """Return FileLoader for a file with this path.
        Start to check file format from biggest part after first dot,
        e.g. for NiftiFile.nii.gz
        at first check 'nii.gz', then check 'gz'
        """
        file_format = path.name.lower()
        while True:
            loader_cls = self.file_loader_registry.processor_cls(file_format)
            if loader_cls is not None:
                return loader_cls

            dot_index = file_format.find('.')
            if dot_index == -1:
                return None

            file_format = file_format[dot_index + 1:]  # dot_index + 1 to remove dot
