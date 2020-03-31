from __future__ import annotations

from typing import Type, Optional

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin
from bsmu.vision_core.data import Data


class FileLoadingManagerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        file_loader_registry_plugin = app.enable_plugin('bsmu.vision.plugins.loaders.registry.FileLoaderRegistryPlugin')
        self.file_loading_manager = FileLoadingManager(file_loader_registry_plugin.file_loader_registry)


class FileLoadingManager(QObject):
    file_loaded = Signal(Data)

    def __init__(self, file_loader_registry: FileLoaderRegistry):
        super().__init__()

        self.file_loader_registry = file_loader_registry

    def can_load_file(self, path: Path) -> bool:
        return self._loader_cls(path) is not None

    def load_file(self, path: Path, **kwargs) -> Optional[Data]:
        print('File loader: load_file')
        if path.exists():
            format_loader_cls = self._loader_cls(path)
            if format_loader_cls is None:
                return None
            format_loader = format_loader_cls()
            data = format_loader.load_file(path, **kwargs)
        else:
            data = None
        self.file_loaded.emit(data)
        return data

    def _loader_cls(self, path: Path) -> Optional[Type[FileLoader]]:
        """Return FileLoader for a file with this path.
        Start to check file format from biggest part after first dot,
        e.g. for NiftiFile.nii.gz
        at first check 'nii.gz', then check 'gz'
        """
        file_format = path.name
        while True:
            loader_cls = self.file_loader_registry.loader_cls(file_format)
            if loader_cls is not None:
                return loader_cls

            dot_index = file_format.find('.')
            if dot_index == -1:
                return None

            file_format = file_format[dot_index + 1:]  # dot_index + 1 to remove dot
