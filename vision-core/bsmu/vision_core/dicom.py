from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision_core.data import Data

if TYPE_CHECKING:
    from pydicom.dataset import FileDataset
    from pathlib import Path


class Dicom(Data):
    def __init__(self, dataset: FileDataset = None, path: Path = None):
        super().__init__(path)

        self.dataset = dataset
        self.pixel_array = self.dataset.pixel_array
