from __future__ import annotations

from bsmu.vision.plugins.loaders.base import FileLoaderPlugin, FileLoader
from bsmu.vision_core.dicom import Dicom

import pydicom
from pydicom.dataset import FileDataset


class MultiFrameDicomFileLoaderPlugin(FileLoaderPlugin):
    def __init__(self, app: App):
        super().__init__(app, MultiFrameDicomFileLoader)


class MultiFrameDicomFileLoader(FileLoader):
    _FORMATS = ('dcm',)

    def _load_file(self, path: Path, **kwargs):
        print('Load Multi-frame DICOM')

        dataset = pydicom.dcmread(str(path))
        return Dicom(dataset, path)



        # from pydicom.data import get_testdata_files
        # filename = get_testdata_files('MR_small.dcm')[0]
        # dataset = pydicom.dcmread(filename)
        print(dataset)
        print('++++++++++++++++')


        print('Name', dataset.PatientName)

        top_level_tags = dataset.dir('')
        for tag in top_level_tags:
            print(f'\t{tag}')
        print(dataset.dir('pos'))
        print(dataset.dir('spac'))
        print(dataset.dir('volume'))

        print(dataset.PatientPosition)
        print(dataset.VolumetricProperties)
        # print(dataset.PlanePositionSequence)
        print(dataset.SliceThickness)


        # from pydicom.datadict import tag_for_keyword
        # tag = tag_for_keyword("PixelSpacing")
        # print('tag', tag)
        # print(dataset.get_item(tag))
        # dataset[tag] = dataset.get_item(tag)._replace(VR="DS")

        # print('spacing', dataset.PixelSpacing)
        # print('spacing', dataset.ImagerPixelSpacing)
        # print('spacing', dataset.NominalScannedPixelSpacing)
        print('----------------')

        data = dataset.pixel_array
        print(type(data), data.shape)
        return
