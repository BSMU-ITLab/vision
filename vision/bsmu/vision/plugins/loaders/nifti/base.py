from __future__ import annotations

import nibabel as nib
import numpy as np

from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader
from bsmu.vision_core.image.base import VolumeImage, SpatialAttrs


class NiftiFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, NiftiFileLoader)


class NiftiFileLoader(FileLoader):
    _FORMATS = ('nii.gz',)

    def _load_file(self, path: Path, **kwargs) -> VolumeImage:
        print('Load NIfTI DICOM')

        nifti_image = nib.load(str(path))

        origin = nifti_image.affine[:3, -1]
        spacing = nifti_image.header.get_zooms()
        # https://simpleitk.readthedocs.io/en/v1.2.4/Documentation/docs/source/fundamentalConcepts.html
        # https://nipy.org/nibabel/dicom/dicom_orientation.html
        direction = nifti_image.affine[:3, :3] / spacing

        print('affine\n', nifti_image.affine)
        print('origin', origin)
        print('spacing', spacing)
        print('direction\n', direction)
        spatial = SpatialAttrs(origin=origin, spacing=spacing, direction=direction)

        return VolumeImage(np.asanyarray(nifti_image.dataobj), path=path, spatial=spatial)  # nifti_image.get_fdata()
