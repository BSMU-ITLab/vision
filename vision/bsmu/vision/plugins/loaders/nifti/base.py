from __future__ import annotations

import nibabel as nib
import numpy as np

from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader
from bsmu.vision_core.image import VolumeImage


class NiftiFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, NiftiFileLoader)


class NiftiFileLoader(FileLoader):
    _FORMATS = ('nii.gz',)

    def _load_file(self, path: Path, **kwargs) -> VolumeImage:
        print('Load NIfTI DICOM')

        nifti_image = nib.load(str(path))
        # return VolumeImage(nifti_image.get_fdata(), path=path)
        return VolumeImage(np.asanyarray(nifti_image.dataobj), path=path)
