from __future__ import annotations

import pydicom

from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader
from bsmu.vision_core.image import VolumeImage


class MultiFrameDicomFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, MultiFrameDicomFileLoader)


class MultiFrameDicomFileLoader(FileLoader):
    _FORMATS = ('dcm',)

    def _load_file(self, path: Path, **kwargs) -> VolumeImage:
        print('Load Multi-frame DICOM')

        dataset = pydicom.dcmread(str(path))
        return VolumeImage(dataset.pixel_array, path=path)
