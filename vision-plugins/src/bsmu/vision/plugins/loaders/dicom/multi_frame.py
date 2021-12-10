from __future__ import annotations

import pydicom

from bsmu.vision.core.image.base import VolumeImage
from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader


class MultiFrameDicomFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self):
        super().__init__(MultiFrameDicomFileLoader)


class MultiFrameDicomFileLoader(FileLoader):
    _FORMATS = ('dcm',)

    def _load_file(self, path: Path, **kwargs) -> VolumeImage:
        print('Load Multi-frame DICOM')

        dataset = pydicom.dcmread(str(path))
        return VolumeImage(dataset.pixel_array, path=path)
