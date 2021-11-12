from __future__ import annotations

from bsmu.vision.core.plugin.processor import ProcessorRegistryPlugin, ProcessorRegistry
from bsmu.vision.plugins.loaders.base import FileLoaderPlugin


class FileLoaderRegistryPlugin(ProcessorRegistryPlugin):
    def __init__(self):
        super().__init__(ProcessorRegistry, FileLoaderPlugin)
