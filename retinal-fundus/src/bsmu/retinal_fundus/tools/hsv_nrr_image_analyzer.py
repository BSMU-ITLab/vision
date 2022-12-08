from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import skimage.io
from PySide6.QtCore import QObject, QPointF
from PySide6.QtWidgets import QMessageBox

import bsmu.vision.core.converters.image as image_converter
from bsmu.retinal_fundus.plugins.ms_predictor import MsPredictionScoreParameter
from bsmu.retinal_fundus.plugins.nrr_hsv_ms_predictor import RetinalFundusNrrHsvMsPredictor, \
    NrrHsvMsPredictionParameter, DiseaseStatus
from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator, NrrBboxParameter
from bsmu.retinal_fundus.plugins.table_visualizer import PatientRetinalFundusRecord, PatientRetinalFundusJournal
from bsmu.retinal_fundus.plugins.disk_region_selector import RetinalFundusDiskRegionSelector, sector_mask
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.palette import Palette
from bsmu.vision.dnn.inferencer import ModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter

if TYPE_CHECKING:
    from typing import Type, Any


class PatientNameObjectParameter(ObjectParameter):
    NAME = 'Patient Name'


class MsStateObjectParameter(ObjectParameter):
    NAME = 'MS State'


class NrrHMeanObjectParameter(ObjectParameter):
    NAME = 'NRR H Mean'


class NrrHStdObjectParameter(ObjectParameter):
    NAME = 'NRR H Std'


class NrrHMinBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR H Min Bin 3'


class NrrHMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR H Max Bin 3'


class NrrSMeanObjectParameter(ObjectParameter):
    NAME = 'NRR S Mean'


class NrrSStdObjectParameter(ObjectParameter):
    NAME = 'NRR S Std'


class NrrSMinBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR S Min Bin 3'


class NrrSMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR S Max Bin 3'


class NrrVMeanObjectParameter(ObjectParameter):
    NAME = 'NRR V Mean'


class NrrVStdObjectParameter(ObjectParameter):
    NAME = 'NRR V Std'


class NrrVMinBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR V Min Bin 3'


class NrrVMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'NRR V Max Bin 3'


class NrrISectorHMeanObjectParameter(ObjectParameter):
    NAME = 'NRR I Sector - H Mean'


class NrrISectorSMeanObjectParameter(ObjectParameter):
    NAME = 'NRR I Sector - S Mean'


class NrrISectorVMeanObjectParameter(ObjectParameter):
    NAME = 'NRR I Sector - V Mean'


class NrrSSectorHMeanObjectParameter(ObjectParameter):
    NAME = 'NRR S Sector - H Mean'


class NrrSSectorSMeanObjectParameter(ObjectParameter):
    NAME = 'NRR S Sector - S Mean'


class NrrSSectorVMeanObjectParameter(ObjectParameter):
    NAME = 'NRR S Sector - V Mean'


class NrrNSectorHMeanObjectParameter(ObjectParameter):
    NAME = 'NRR N Sector - H Mean'


class NrrNSectorSMeanObjectParameter(ObjectParameter):
    NAME = 'NRR N Sector - S Mean'


class NrrNSectorVMeanObjectParameter(ObjectParameter):
    NAME = 'NRR N Sector - V Mean'


class NrrTSectorHMeanObjectParameter(ObjectParameter):
    NAME = 'NRR T Sector - H Mean'


class NrrTSectorSMeanObjectParameter(ObjectParameter):
    NAME = 'NRR T Sector - S Mean'


class NrrTSectorVMeanObjectParameter(ObjectParameter):
    NAME = 'NRR T Sector - V Mean'


class DiskRegionHMeanObjectParameter(ObjectParameter):
    NAME = 'Disk Region H Mean'


class DiskRegionHStdObjectParameter(ObjectParameter):
    NAME = 'Disk Region H Std'


class DiskRegionHMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region H Min Bin 3'


class DiskRegionHMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region H Max Bin 3'


class DiskRegionSMeanObjectParameter(ObjectParameter):
    NAME = 'Disk Region S Mean'


class DiskRegionSStdObjectParameter(ObjectParameter):
    NAME = 'Disk Region S Std'


class DiskRegionSMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region S Min Bin 3'


class DiskRegionSMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region S Max Bin 3'


class DiskRegionVMeanObjectParameter(ObjectParameter):
    NAME = 'Disk Region V Mean'


class DiskRegionVStdObjectParameter(ObjectParameter):
    NAME = 'Disk Region V Std'


class DiskRegionVMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region V Min Bin 3'


class DiskRegionVMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk Region V Max Bin 3'


class DiskHMeanObjectParameter(ObjectParameter):
    NAME = 'Disk H Mean'


class DiskHStdObjectParameter(ObjectParameter):
    NAME = 'Disk H Std'


class DiskHMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk H Min Bin 3'


class DiskHMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk H Max Bin 3'


class DiskSMeanObjectParameter(ObjectParameter):
    NAME = 'Disk S Mean'


class DiskSStdObjectParameter(ObjectParameter):
    NAME = 'Disk S Std'


class DiskSMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk S Min Bin 3'


class DiskSMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk S Max Bin 3'


class DiskVMeanObjectParameter(ObjectParameter):
    NAME = 'Disk V Mean'


class DiskVStdObjectParameter(ObjectParameter):
    NAME = 'Disk V Std'


class DiskVMinBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk V Min Bin 3'


class DiskVMaxBin3ObjectParameter(ObjectParameter):
    NAME = 'Disk V Max Bin 3'


class JournalExporter(QObject):
    PATIENT_NAME_FIELD_NAME = 'Patient'
    IMAGE_NAME_FIELD_NAME = 'Image Name'

    def export_to_csv(self, journal: PatientRetinalFundusJournal, csv_path: Path):
        print('export to csv')

        # file_name, selected_filter = QFileDialog.getSaveFileName(
        #     parent=None, caption='Export to CSV', filter='CSV (*.csv)')
        # if not file_name:
        #     return
        file_name = csv_path

        try:
            csv_file = open(file_name, 'w', encoding='utf-8-sig', newline='')
        except PermissionError:
            print('PermissionError')
            QMessageBox.warning(None, 'File Open Error',
                                'Cannot open the file due to a permission error.\n'
                                'The file may be opened in another program.')
        else:
            with csv_file:
                float_parameter_types = [
                    # NRR HSV parameters
                    NrrHMeanObjectParameter,
                    NrrSMeanObjectParameter,
                    NrrVMeanObjectParameter,
                    NrrHStdObjectParameter,
                    NrrSStdObjectParameter,
                    NrrVStdObjectParameter,
                    NrrHMinBin3ObjectParameter,
                    NrrSMinBin3ObjectParameter,
                    NrrVMinBin3ObjectParameter,
                    NrrHMaxBin3ObjectParameter,
                    NrrSMaxBin3ObjectParameter,
                    NrrVMaxBin3ObjectParameter,
                    # NRR HSV parameters of ISNT-sectors
                    NrrISectorHMeanObjectParameter,
                    NrrISectorSMeanObjectParameter,
                    NrrISectorVMeanObjectParameter,
                    NrrSSectorHMeanObjectParameter,
                    NrrSSectorSMeanObjectParameter,
                    NrrSSectorVMeanObjectParameter,
                    NrrNSectorHMeanObjectParameter,
                    NrrNSectorSMeanObjectParameter,
                    NrrNSectorVMeanObjectParameter,
                    NrrTSectorHMeanObjectParameter,
                    NrrTSectorSMeanObjectParameter,
                    NrrTSectorVMeanObjectParameter,
                    # Small disk region HSV parameters
                    DiskRegionHMeanObjectParameter,
                    DiskRegionSMeanObjectParameter,
                    DiskRegionVMeanObjectParameter,
                    DiskRegionHStdObjectParameter,
                    DiskRegionSStdObjectParameter,
                    DiskRegionVStdObjectParameter,
                    DiskRegionHMinBin3ObjectParameter,
                    DiskRegionSMinBin3ObjectParameter,
                    DiskRegionVMinBin3ObjectParameter,
                    DiskRegionHMaxBin3ObjectParameter,
                    DiskRegionSMaxBin3ObjectParameter,
                    DiskRegionVMaxBin3ObjectParameter,
                    # Disk HSV parameters
                    DiskHMeanObjectParameter,
                    DiskSMeanObjectParameter,
                    DiskVMeanObjectParameter,
                    DiskHStdObjectParameter,
                    DiskSStdObjectParameter,
                    DiskVStdObjectParameter,
                    DiskHMinBin3ObjectParameter,
                    DiskSMinBin3ObjectParameter,
                    DiskVMinBin3ObjectParameter,
                    DiskHMaxBin3ObjectParameter,
                    DiskSMaxBin3ObjectParameter,
                    DiskVMaxBin3ObjectParameter,
                ]

                field_names = [
                    self.PATIENT_NAME_FIELD_NAME,
                    self.IMAGE_NAME_FIELD_NAME,
                    MsStateObjectParameter.NAME,
                ] + [parameter_type.NAME for parameter_type in float_parameter_types]

                writer = csv.DictWriter(csv_file, delimiter=';', fieldnames=field_names)
                writer.writeheader()

                for record in journal.records:
                    writer.writerow({
                        self.PATIENT_NAME_FIELD_NAME: record.parameter_value_str_by_type(PatientNameObjectParameter),
                        self.IMAGE_NAME_FIELD_NAME: record.image.path.name,
                        MsStateObjectParameter.NAME: int(record.parameter_value_by_type(MsStateObjectParameter)),
                    } | dict(parameter_name_float_value_str_tuple(parameter_type, record)
                             for parameter_type in float_parameter_types))


def parameter_name_float_value_str_tuple(
        parameter_type: Type[ObjectParameter], record: PatientRetinalFundusRecord) -> tuple[str, str]:
    return parameter_type.NAME, parameter_float_value_to_str(record.parameter_value_by_type(parameter_type))


def parameter_float_value_to_str(value: float) -> str:
    if value is None:
        return '?'
    return f'{value:.6f}'.replace('.', ',')


def analyze_record_image(
        record: PatientRetinalFundusRecord,
        disk_segmenter: DnnSegmenter,
        cup_segmenter: DnnSegmenter,
        vessels_segmenter: DnnSegmenter,
        dnn_ms_predictor: DnnPredictor,
        nrr_mask_calculator: RetinalFundusNrrMaskCalculator,
        hsv_ms_predictor: RetinalFundusNrrHsvMsPredictor,
) -> bool:
    image = record.image.pixels

    # Disk segmentation
    disk_mask_pixels, disk_bbox = disk_segmenter.segment_largest_connected_component_and_return_mask_with_bbox(image)
    disk_mask_pixels = image_converter.normalized_uint8(disk_mask_pixels)
    disk_mask_layer = record.layered_image.add_layer_from_image(
        FlatImage(array=disk_mask_pixels, palette=Palette.default_binary(255, [102, 255, 128])),
        PatientRetinalFundusRecord.DISK_MASK_LAYER_NAME)

    record.disk_bbox = disk_bbox

    if disk_bbox is None:
        return False

        # cup_mask_pixels = np.zeros_like(disk_mask_pixels)
        # cup_mask_layer = record.layered_image.add_layer_from_image(
        #     FlatImage(array=cup_mask_pixels, palette=Palette.default_binary(255, [189, 103, 255])),
        #     PatientRetinalFundusRecord.CUP_MASK_LAYER_NAME)
        #
        # # Vessels segmentation
        # self._segment_vessels(record, image)
        # return

    disk_region_bbox = disk_bbox.margins_added(round((disk_bbox.width + disk_bbox.height) / 2))
    disk_region_bbox.clip_to_shape(image.shape)

    disk_region_image_pixels = record.image.bboxed_pixels(disk_region_bbox)
    # data.add_layer_from_image(FlatImage(disk_region_image_pixels), name='disk-region')

    # disk_region_mask_pixels = np.zeros_like(disk_mask_pixels)
    # disk_region_mask_pixels[disk_region_bbox.top:disk_region_bbox.bottom, disk_region_bbox.left:disk_region_bbox.right,
    # ...] = 255
    # disk_region_mask_layer = record.layered_image.add_layer_from_image(
    #     FlatImage(disk_region_mask_pixels, self._disk_mask_palette),
    #     PatientRetinalFundusRecord.DISK_REGION_MASK_LAYER_NAME)

    # Optic cup segmentation
    cup_mask_pixels_on_disk_region, cup_bbox = \
        cup_segmenter.segment_largest_connected_component_and_return_mask_with_bbox(disk_region_image_pixels)

    cup_mask_pixels_on_disk_region = image_converter.normalized_uint8(cup_mask_pixels_on_disk_region)
    cup_mask_pixels = np.zeros_like(disk_mask_pixels)
    cup_mask_pixels[disk_region_bbox.top:disk_region_bbox.bottom, disk_region_bbox.left:disk_region_bbox.right, ...] = \
        cup_mask_pixels_on_disk_region
    cup_mask_layer = record.layered_image.add_layer_from_image(
            FlatImage(array=cup_mask_pixels, palette=Palette.default_binary(255, [189, 103, 255])),
            PatientRetinalFundusRecord.CUP_MASK_LAYER_NAME)

    # Vessels segmentation
    vessels_mask_pixels = vessels_segmenter.segment_on_splitted_into_tiles(image)

    vessels_mask_pixels = image_converter.normalized_uint8(vessels_mask_pixels)
    vessels_mask_layer = record.layered_image.add_layer_from_image(
        FlatImage(array=vessels_mask_pixels, palette=Palette.default_soft([102, 183, 255])),
        PatientRetinalFundusRecord.VESSELS_MASK_LAYER_NAME)

    record.calculate_params()

    """
    # Predict MS using DNN
    disk_region_bbox = record.disk_bbox.margins_added(
        round((record.disk_bbox.width + record.disk_bbox.height) / 2))
    disk_region_bbox.clip_to_shape(record.image.shape)
    disk_region_image = disk_region_bbox.pixels(record.image.pixels)

    ms_prediction_score = dnn_ms_predictor.predict(disk_region_image)
    ms_prediction_score_parameter = MsPredictionScoreParameter(ms_prediction_score)
    ms_prediction_score_parameter = record.add_parameter_or_modify_value(ms_prediction_score_parameter)
    """


    # Predict MS using classical method (HSV)
    # Calculate record_nrr_mask
    nrr_mask_calculator._calculate_nrr_bbox_for_record(record)
    nrr_mask_calculator._calculate_nrr_mask_for_record(record)
    analyze_record_hsv_parameters(record)
    """
    hsv_ms_predictor._predict_for_record(record)
    """

    # Print values and check it
    # print(f'DNN Result: {record.parameter_value_str_by_type(MsPredictionScoreParameter)}\t'
    #       f'HSV Result: {record.parameter_value_str_by_type(NrrHsvMsPredictionParameter)}')

    return True


def analyze_record_hsv_parameters(record: PatientRetinalFundusRecord):
    if (nrr_mask := RetinalFundusNrrMaskCalculator.record_nrr_mask(record)) is None:
        return

    if (nrr_bbox := record.parameter_value_by_type(NrrBboxParameter)) is None:
        return

    nrr_image_in_region = nrr_bbox.pixels(record.image.pixels)
    nrr_mask_in_region = nrr_bbox.pixels(nrr_mask.pixels)

    nrr_image_in_region = nrr_image_in_region.astype(np.float32) / 255
    nrr_region_image_hsv = cv.cvtColor(nrr_image_in_region, cv.COLOR_RGB2HSV)
    nrr_region_image_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

    nrr_bool_mask_in_region = nrr_mask_in_region > 127
    nrr_hsv_flatten_pixels = nrr_region_image_hsv[nrr_bool_mask_in_region]

    nrr_hsv_mean, nrr_hsv_std, nrr_hsv_min_bin_3, nrr_hsv_max_bin_3 = calculate_hsv_parameters(nrr_hsv_flatten_pixels)

    add_record_parameter(record, NrrHMeanObjectParameter, nrr_hsv_mean[0])
    add_record_parameter(record, NrrSMeanObjectParameter, nrr_hsv_mean[1])
    add_record_parameter(record, NrrVMeanObjectParameter, nrr_hsv_mean[2])

    add_record_parameter(record, NrrHStdObjectParameter, nrr_hsv_std[0])
    add_record_parameter(record, NrrSStdObjectParameter, nrr_hsv_std[1])
    add_record_parameter(record, NrrVStdObjectParameter, nrr_hsv_std[2])

    add_record_parameter(record, NrrHMinBin3ObjectParameter, nrr_hsv_min_bin_3[0])
    add_record_parameter(record, NrrSMinBin3ObjectParameter, nrr_hsv_min_bin_3[1])
    add_record_parameter(record, NrrVMinBin3ObjectParameter, nrr_hsv_min_bin_3[2])

    add_record_parameter(record, NrrHMaxBin3ObjectParameter, nrr_hsv_max_bin_3[0])
    add_record_parameter(record, NrrSMaxBin3ObjectParameter, nrr_hsv_max_bin_3[1])
    add_record_parameter(record, NrrVMaxBin3ObjectParameter, nrr_hsv_max_bin_3[2])

    # Analyze ISNT-sectors
    small_disk_region = record.disk_bbox.scaled(1.2, 1.2)
    small_disk_region.clip_to_shape(record.image.shape)
    small_disk_region_image_pixels = record.image.bboxed_pixels(small_disk_region)
    disk_center = QPointF(small_disk_region.width, small_disk_region.height) / 2

    isnt_sectors = RetinalFundusDiskRegionSelector.ISNT_SECTORS_PRESET.sectors()
    n_sector, i_sector, t_sector, s_sector = isnt_sectors
    parameters_by_sector = {n_sector.name: [NrrNSectorHMeanObjectParameter, NrrNSectorSMeanObjectParameter, NrrNSectorVMeanObjectParameter],
                            i_sector.name: [NrrISectorHMeanObjectParameter, NrrISectorSMeanObjectParameter, NrrISectorVMeanObjectParameter],
                            t_sector.name: [NrrTSectorHMeanObjectParameter, NrrTSectorSMeanObjectParameter, NrrTSectorVMeanObjectParameter],
                            s_sector.name: [NrrSSectorHMeanObjectParameter, NrrSSectorSMeanObjectParameter, NrrSSectorVMeanObjectParameter]}
    for sector in isnt_sectors:
        curr_sector_mask = sector_mask(
            small_disk_region_image_pixels.shape[:2],
            (round(disk_center.y()), round(disk_center.x())),
            (sector.start_angle, sector.end_angle))

        nrr_mask_copy = np.copy(nrr_mask.pixels)
        # Analyze only selected sector
        nrr_mask_in_small_disk_region = small_disk_region.pixels(nrr_mask_copy)
        nrr_mask_in_small_disk_region[curr_sector_mask == 0] = 0

        cropped_nrr_mask = nrr_bbox.pixels(nrr_mask_copy)
        cropped_nrr_float_mask = cropped_nrr_mask / 255

        cropped_nrr_bool_mask = cropped_nrr_float_mask > 0.5
        if not cropped_nrr_bool_mask.any():
            continue

        nrr_hsv_flatten_pixels_in_sector = nrr_region_image_hsv[cropped_nrr_bool_mask]

        sector_hsv_mean = np.mean(nrr_hsv_flatten_pixels_in_sector, axis=0)

        sector_parameters = parameters_by_sector[sector.name]
        add_record_parameter(record, sector_parameters[0], sector_hsv_mean[0])
        add_record_parameter(record, sector_parameters[1], sector_hsv_mean[1])
        add_record_parameter(record, sector_parameters[2], sector_hsv_mean[2])

    # Analyze small disk region HSV parameters
    small_disk_region_image_pixels = small_disk_region_image_pixels.astype(np.float32) / 255
    small_disk_region_image_hsv = cv.cvtColor(small_disk_region_image_pixels, cv.COLOR_RGB2HSV)
    small_disk_region_image_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

    small_disk_region_flatten_hsv = small_disk_region_image_hsv.reshape(-1, small_disk_region_image_hsv.shape[-1])
    small_disk_region_hsv_mean, small_disk_region_hsv_std, small_disk_region_hsv_min_bin_3, small_disk_region_hsv_max_bin_3 \
        = calculate_hsv_parameters(small_disk_region_flatten_hsv)

    add_record_parameter(record, DiskRegionHMeanObjectParameter, small_disk_region_hsv_mean[0])
    add_record_parameter(record, DiskRegionSMeanObjectParameter, small_disk_region_hsv_mean[1])
    add_record_parameter(record, DiskRegionVMeanObjectParameter, small_disk_region_hsv_mean[2])

    add_record_parameter(record, DiskRegionHStdObjectParameter, small_disk_region_hsv_std[0])
    add_record_parameter(record, DiskRegionSStdObjectParameter, small_disk_region_hsv_std[1])
    add_record_parameter(record, DiskRegionVStdObjectParameter, small_disk_region_hsv_std[2])

    add_record_parameter(record, DiskRegionHMinBin3ObjectParameter, small_disk_region_hsv_min_bin_3[0])
    add_record_parameter(record, DiskRegionSMinBin3ObjectParameter, small_disk_region_hsv_min_bin_3[1])
    add_record_parameter(record, DiskRegionVMinBin3ObjectParameter, small_disk_region_hsv_min_bin_3[2])

    add_record_parameter(record, DiskRegionHMaxBin3ObjectParameter, small_disk_region_hsv_max_bin_3[0])
    add_record_parameter(record, DiskRegionSMaxBin3ObjectParameter, small_disk_region_hsv_max_bin_3[1])
    add_record_parameter(record, DiskRegionVMaxBin3ObjectParameter, small_disk_region_hsv_max_bin_3[2])

    # Analyze disk HSV parameters
    disk_image_in_region = record.image.bboxed_pixels(record.disk_bbox)
    disk_mask_in_region = record.disk_mask.bboxed_pixels(record.disk_bbox)

    disk_image_in_region = disk_image_in_region.astype(np.float32) / 255
    disk_image_in_region_hsv = cv.cvtColor(disk_image_in_region, cv.COLOR_RGB2HSV)
    disk_image_in_region_hsv[..., 0] /= 360  # Normalize H-channel to [0; 1] range

    disk_bool_mask_in_region = disk_mask_in_region > 127
    disk_hsv_flatten_pixels = disk_image_in_region_hsv[disk_bool_mask_in_region]

    disk_hsv_mean, disk_hsv_std, disk_hsv_min_bin_3, disk_hsv_max_bin_3 = \
        calculate_hsv_parameters(disk_hsv_flatten_pixels)

    add_record_parameter(record, DiskHMeanObjectParameter, disk_hsv_mean[0])
    add_record_parameter(record, DiskSMeanObjectParameter, disk_hsv_mean[1])
    add_record_parameter(record, DiskVMeanObjectParameter, disk_hsv_mean[2])

    add_record_parameter(record, DiskHStdObjectParameter, disk_hsv_std[0])
    add_record_parameter(record, DiskSStdObjectParameter, disk_hsv_std[1])
    add_record_parameter(record, DiskVStdObjectParameter, disk_hsv_std[2])

    add_record_parameter(record, DiskHMinBin3ObjectParameter, disk_hsv_min_bin_3[0])
    add_record_parameter(record, DiskSMinBin3ObjectParameter, disk_hsv_min_bin_3[1])
    add_record_parameter(record, DiskVMinBin3ObjectParameter, disk_hsv_min_bin_3[2])

    add_record_parameter(record, DiskHMaxBin3ObjectParameter, disk_hsv_max_bin_3[0])
    add_record_parameter(record, DiskSMaxBin3ObjectParameter, disk_hsv_max_bin_3[1])
    add_record_parameter(record, DiskVMaxBin3ObjectParameter, disk_hsv_max_bin_3[2])


def calculate_hsv_parameters(hsv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    hsv_mean = np.mean(hsv, axis=0)
    hsv_std = np.std(hsv, axis=0)
    # hsv_min = np.min(hsv, axis=0)
    # hsv_max = np.max(hsv, axis=0)

    kth = int(hsv.shape[0] * 0.03)  # 3% of max/min pixels
    hsv_min_bin_3 = np.mean(np.partition(hsv, kth, axis=0)[:kth, :], axis=0)
    hsv_max_bin_3 = np.mean(np.partition(hsv, -kth, axis=0)[-kth:, :], axis=0)

    return hsv_mean, hsv_std, hsv_min_bin_3, hsv_max_bin_3


def add_record_parameter(record: PatientRetinalFundusRecord, parameter_type: Type[ObjectParameter], value: Any):
    parameter = parameter_type(value)
    record.add_parameter(parameter)


def analyze_dir_images(image_dir: Path, ms_true_state: bool, save_csv_path: Path):
    disk_segmenter_model_params = DnnModelParams(
        path=Path(r'D:\Projects\vision\retinal-fundus\src\bsmu\retinal_fundus\plugins\dnn-models\disk-model-005.onnx'),
        input_size=(352, 352, 3),
        preprocessing_mode='image-net-tf')
    disk_segmenter = DnnSegmenter(disk_segmenter_model_params)

    cup_segmenter_model_params = DnnModelParams(
        path=Path(r'D:\Projects\vision\retinal-fundus\src\bsmu\retinal_fundus\plugins\dnn-models\cup-model-006.onnx'),
        input_size=(352, 352, 3),
        preprocessing_mode='image-net-tf')
    cup_segmenter = DnnSegmenter(cup_segmenter_model_params)

    vessels_segmenter_model_params = DnnModelParams(
        path=Path(r'D:\Projects\vision\retinal-fundus\src\bsmu\retinal_fundus\plugins\dnn-models\vessels-model-083.onnx'),
        input_size=(352, 352, 3),
        preprocessing_mode='image-net-torch')
    vessels_segmenter = DnnSegmenter(vessels_segmenter_model_params)

    dnn_ms_predictor_model_params = DnnModelParams(
        path=Path(r'D:\Projects\vision\retinal-fundus\src\bsmu\retinal_fundus\plugins\dnn-models\ms-model-052.onnx'),
        input_size=(256, 256, 3),
        preprocessing_mode='image-net-torch')
    dnn_ms_predictor = DnnPredictor(dnn_ms_predictor_model_params)

    nrr_mask_calculator = RetinalFundusNrrMaskCalculator()
    hsv_ms_predictor = RetinalFundusNrrHsvMsPredictor(None)

    journal = PatientRetinalFundusJournal()

    for patient_dir in image_dir.iterdir():
        print(f'\n\nPatient: {patient_dir.name}')
        if not patient_dir.is_dir():
            continue

        patient_name_object_parameter = PatientNameObjectParameter()
        patient_name_object_parameter.value = patient_dir.name

        for image_path in patient_dir.iterdir():
            if not image_path.is_file():
                continue

            if image_path.suffix.lower() not in ['.bmp', '.png', '.jpeg', '.jpg', '.tiff']:
                continue

            print(f'Image: {image_path.name}')
            image = skimage.io.imread(str(image_path))

            record = PatientRetinalFundusRecord.from_flat_image(FlatImage(image, path=image_path))
            journal.add_record(record)

            record.add_parameter_or_modify_value(patient_name_object_parameter)

            analyzed = analyze_record_image(
                record, disk_segmenter, cup_segmenter, vessels_segmenter, dnn_ms_predictor, nrr_mask_calculator,
                hsv_ms_predictor)
            record.add_parameter(MsStateObjectParameter(ms_true_state))
            if not analyzed:
                print('!!! Cannot analyze the image!')
                continue

    # Save journal values into CSV
    print(f'journal len: {len(journal.records)}')

    journal_csv_exporter = JournalExporter()
    journal_csv_exporter.export_to_csv(journal, save_csv_path)


def run():
    # image_dir = Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted\part-3\norm-east')
    image_dir = Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted\part-3\norm-east')
    # image_dir = Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted\TEST_part1\ms')
    csv_path = image_dir / 'HSV-AnalysisResult-Extended.csv'
    analyze_dir_images(image_dir, False, csv_path)


if __name__ == '__main__':
    run()
