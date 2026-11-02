from __future__ import annotations

from bsmu.vision.core.plugins.processor.registry import ProcessorRegistryPlugin, ProcessorRegistry
from bsmu.vision.plugins.io.file import FileReaderPlugin


class FileReaderRegistryPlugin(ProcessorRegistryPlugin):
    def __init__(self):
        super().__init__(ProcessorRegistry, FileReaderPlugin)
