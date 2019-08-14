from __future__ import annotations

from typing import Type

from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader


class ImageFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App, file_loader_cls: Type[FileLoader]):
        super().__init__(app, file_loader_cls)


class ImageFileLoader(FileLoader):
    pass
