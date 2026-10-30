from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from typing import Type

    from bsmu.vision.core.io import FileWriter


class FileWriterPlugin(Plugin):
    def __init__(self, file_writer_cls: Type[FileWriter]):
        super().__init__()

        self._file_writer_cls = file_writer_cls
