from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.plugins.processor import ProcessorPlugin

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.core.io import FileReader


class FileReaderPlugin(ProcessorPlugin):
    def __init__(self, file_reader_cls: Type[FileReader]):
        super().__init__(file_reader_cls)
