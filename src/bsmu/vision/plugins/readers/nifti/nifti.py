from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import nibabel as nib
import numpy as np

from bsmu.vision.core.image import VolumeImage, SpatialAttrs
from bsmu.vision.plugins.readers.file import FileReaderPlugin, FileReader

if TYPE_CHECKING:
    from pathlib import Path


class NiftiFileReaderPlugin(FileReaderPlugin):
    def __init__(self):
        super().__init__(NiftiFileReader)


class NiftiFileReader(FileReader):
    _FORMATS = ('nii.gz',)

    def _read_file(self, path: Path, palette=None, **kwargs) -> VolumeImage:
        logging.info('Read NIfTI DICOM')

        nifti_image = nib.load(str(path))

        origin = nifti_image.affine[:3, -1]
        spacing = nifti_image.header.get_zooms()
        # https://simpleitk.readthedocs.io/en/v1.2.4/Documentation/docs/source/fundamentalConcepts.html
        # https://nipy.org/nibabel/dicom/dicom_orientation.html
        direction = nifti_image.affine[:3, :3] / spacing

        logging.info(f'Affine:\n{nifti_image.affine}\n'
                     f'Origin: {origin}\n'
                     f'Spacing: {spacing}\n'
                     f'Direction:\n{direction}')
        spatial = SpatialAttrs(origin=origin, spacing=spacing, direction=direction)

        return VolumeImage(np.asanyarray(nifti_image.dataobj), palette=palette, path=path, spatial=spatial)  # nifti_image.get_fdata()
