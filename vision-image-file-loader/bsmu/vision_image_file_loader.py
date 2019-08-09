from typing import Type

from bsmu.vision_file_loader import FileLoaderPlugin, FileLoader


class ImageFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App, file_loader_cls: Type[FileLoader]):
        super().__init__(app, file_loader_cls)


class ImageFileLoader(FileLoader):
    pass
