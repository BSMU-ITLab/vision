import abc
import inspect
from typing import Type

from PySide2.QtCore import QObject, Signal

from bsmu.vision.plugin import Plugin


class FileLoaderPlugin(Plugin):
    def __init__(self, app: App, file_loader_cls: Type[FileLoader]):
        super().__init__(app)

        self.file_loader_cls = file_loader_cls

        file_loader_registry_plugin = app.enable_plugin('bsmu.vision_file_loader_registry.FileLoaderRegistryPlugin')
        self.file_loader_registry = file_loader_registry_plugin.file_loader_registry

    def _enable(self):
        self.file_loader_registry.register_loader_cls(self.file_loader_cls)

    def _disable(self):
        self.file_loader_registry.unregister_loader_cls(self.file_loader_cls)


class FileLoaderMeta(abc.ABCMeta, type(QObject)):
    _FORMATS = ()

    def __new__(mcls, name, bases, namespace):
        print('Meta new')  #%
        print(type(QObject))  #%
        cls = super().__new__(mcls, name, bases, namespace)

        if not inspect.isabstract(cls) and not cls.formats:
            raise NotImplementedError('Subclass must define formats attribute')

        return cls

    @property
    def formats(cls) -> tuple:
        return cls._FORMATS


class FileLoader(QObject, metaclass=FileLoaderMeta):
    #% _FORMATS = ()

    file_loaded = Signal(Data)

    @property
    def formats(self):
        return type(self).formats

    def load_file(self, path: Path) -> Data:
        data = self._load_file(path)
        self.file_loaded.emit(data)
        return data

    @abc.abstractmethod
    def _load_file(self, path: Path) -> Data:
        ...
