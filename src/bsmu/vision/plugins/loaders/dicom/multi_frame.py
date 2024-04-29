from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pydicom

from bsmu.vision.core.image.base import VolumeImage
from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader

if TYPE_CHECKING:
    from pathlib import Path


class MultiFrameDicomFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self):
        super().__init__(MultiFrameDicomFileLoader)


class MultiFrameDicomFileLoader(FileLoader):
    _FORMATS = ('dcm',)

    def _load_file(self, path: Path, **kwargs) -> VolumeImage:
        logging.info('Load Multi-frame DICOM')

        dataset = pydicom.dcmread(str(path))
        return VolumeImage(dataset.pixel_array, path=path)
