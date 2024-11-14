from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins import Plugin
from bsmu.vision.core.task import FnTask

if TYPE_CHECKING:
    from typing import Type
    from pathlib import Path

    from bsmu.vision.core.task import Task
    from bsmu.vision.plugins.readers.file import FileReader
    from bsmu.vision.plugins.readers.registry import FileReaderRegistryPlugin
    from bsmu.vision.plugins.storages.task import TaskStorage, TaskStoragePlugin


class FileReadingManagerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'file_reader_registry_plugin': 'bsmu.vision.plugins.readers.registry.FileReaderRegistryPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task.TaskStoragePlugin',
    }

    def __init__(self, file_reader_registry_plugin: FileReaderRegistryPlugin, task_storage_plugin: TaskStoragePlugin):
        super().__init__()

        self._file_reader_registry_plugin = file_reader_registry_plugin
        self._task_storage_plugin = task_storage_plugin

        self._file_reading_manager: FileReadingManager | None = None

    @property
    def file_reading_manager(self) -> FileReadingManager:
        return self._file_reading_manager

    def _enable(self):
        self._file_reading_manager = FileReadingManager(
            self._file_reader_registry_plugin.processor_registry, self._task_storage_plugin.task_storage)

    def _disable(self):
        self._file_reading_manager = None


class FileReadingManager(QObject):
    file_read = Signal(Data)

    def __init__(self, file_reader_registry: FileReaderRegistry, task_storage: TaskStorage | None = None):
        super().__init__()

        self.file_reader_registry = file_reader_registry
        self._task_storage = task_storage

    def can_read_file(self, path: Path) -> bool:
        return self._reader_cls(path) is not None

    def read_file(self, path: Path, **kwargs) -> Data | None:
        logging.info(f'Read file: {path}')
        data = None
        if path.exists():
            format_reader_cls = self._reader_cls(path)
            if format_reader_cls is not None:
                format_reader = format_reader_cls()
                data = format_reader.read_file(path, **kwargs)
            else:
                logging.info(f'Cannot read the {path} file, because suitable reader is not found')
        else:
            logging.info(f'Cannot read the {path} file, because it is not exist')
        self.file_read.emit(data)
        return data

    def read_file_async(self, path: Path, **kwargs) -> Task:
        return ThreadPool.call_async(
            self.read_file,
            path,
            **kwargs,
        )

    def read_file_async_and_add_task_into_task_storage(self, path: Path, **kwargs) -> Task:
        file_reading_task = FnTask(self.read_file, f'File Reading [{path.name}]')
        if self._task_storage is not None:
            self._task_storage.add_item(file_reading_task)
        ThreadPool.run_async_task_with_args(file_reading_task, path, **kwargs)
        return file_reading_task

    def _reader_cls(self, path: Path) -> Type[FileReader] | None:
        """Return FileReader for a file with this path.
        Start to check file format from the biggest part after first dot,
        e.g. for NiftiFile.nii.gz
        at first check 'nii.gz', then check 'gz'
        """
        file_format = path.name.lower()
        while True:
            reader_cls = self.file_reader_registry.processor_cls(file_format)
            if reader_cls is not None:
                return reader_cls

            dot_index = file_format.find('.')
            if dot_index == -1:
                return None

            file_format = file_format[dot_index + 1:]  # dot_index + 1 to remove dot
