import csv
import shutil
from pathlib import Path

import numpy as np
import skimage.io
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

import bsmu.vision.core.converters.image as image_converter
from bsmu.retinal_fundus.plugins.ms_predictor import MsPredictionScoreParameter
from bsmu.retinal_fundus.plugins.nrr_hsv_ms_predictor import RetinalFundusNrrHsvMsPredictor, \
    NrrHsvMsPredictionParameter, DiseaseStatus
from bsmu.retinal_fundus.plugins.nrr_mask_calculator import RetinalFundusNrrMaskCalculator
from bsmu.retinal_fundus.plugins.table_visualizer import PatientRetinalFundusRecord, PatientRetinalFundusJournal
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.palette import Palette
from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.predictor import Predictor as DnnPredictor
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter


class PatientNameObjectParameter(ObjectParameter):
    NAME = 'Patient Name'


class JournalExporter(QObject):
    PATIENT_NAME_FIELD_NAME = 'Patient'
    IMAGE_NAME_FIELD_NAME = 'Image Name'
    DNN_MS_RESULT_FIELD_NAME = 'DNN Result'
    DNN_MS_ROUNDED_RESULT_FIELD_NAME = 'DNN Rounded Result'
    HSV_MS_RESULT_FIELD_NAME = 'HSV Result'

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
                field_names = [
                    self.PATIENT_NAME_FIELD_NAME,
                    self.IMAGE_NAME_FIELD_NAME,
                    self.DNN_MS_RESULT_FIELD_NAME,
                    self.DNN_MS_ROUNDED_RESULT_FIELD_NAME,
                    self.HSV_MS_RESULT_FIELD_NAME,
                ]

                writer = csv.DictWriter(csv_file, delimiter=';', fieldnames=field_names)
                writer.writeheader()

                for record in journal.records:
                    writer.writerow({
                        self.PATIENT_NAME_FIELD_NAME: record.parameter_value_str_by_type(PatientNameObjectParameter),
                        self.IMAGE_NAME_FIELD_NAME: record.image.path.stem,
                        self.DNN_MS_RESULT_FIELD_NAME:
                            record.parameter_value_str_by_type(MsPredictionScoreParameter).replace('.', ','),
                        self.DNN_MS_ROUNDED_RESULT_FIELD_NAME:
                            round(record.parameter_value_by_type(MsPredictionScoreParameter)),
                        self.HSV_MS_RESULT_FIELD_NAME:
                            1 if record.parameter_value_by_type(NrrHsvMsPredictionParameter) == DiseaseStatus.PATHOLOGY else 0,
                    })


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


    # Predict MS using DNN
    disk_region_bbox = record.disk_bbox.margins_added(
        round((record.disk_bbox.width + record.disk_bbox.height) / 2))
    disk_region_bbox.clip_to_shape(record.image.shape)
    disk_region_image = disk_region_bbox.pixels(record.image.pixels)

    ms_prediction_score = dnn_ms_predictor.predict(disk_region_image)
    ms_prediction_score_parameter = MsPredictionScoreParameter(ms_prediction_score)
    ms_prediction_score_parameter = record.add_parameter_or_modify_value(ms_prediction_score_parameter)


    # Predict MS using classical method (HSV)
    # Calculate record_nrr_mask
    nrr_mask_calculator._calculate_nrr_bbox_for_record(record)
    nrr_mask_calculator._calculate_nrr_mask_for_record(record)
    hsv_ms_predictor._predict_for_record(record)


    # Print values and check it
    print(f'DNN Result: {record.parameter_value_str_by_type(MsPredictionScoreParameter)}\t'
          f'HSV Result: {record.parameter_value_str_by_type(NrrHsvMsPredictionParameter)}')

    return True


def analyze_dir_images(image_dir: Path, ms_true_state: bool, save_csv_path: Path, wrong_result_save_path: Path):
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
                record, disk_segmenter, cup_segmenter, vessels_segmenter, dnn_ms_predictor, nrr_mask_calculator, hsv_ms_predictor)
            if not analyzed:
                print('!!! Cannot analyze the image!')
                continue

            dnn_ms_prediction_state = bool(round(record.parameter_value_by_type(MsPredictionScoreParameter)))
            hsv_ms_prediction_state = True if record.parameter_value_by_type(NrrHsvMsPredictionParameter) == DiseaseStatus.PATHOLOGY else False
            if dnn_ms_prediction_state != ms_true_state and hsv_ms_prediction_state != ms_true_state:
                shutil.copyfile(image_path, wrong_result_save_path / image_path.name)


    # Save journal values into CSV
    print(f'journal len: {len(journal.records)}')

    journal_csv_exporter = JournalExporter()
    journal_csv_exporter.export_to_csv(journal, save_csv_path)


if __name__ == '__main__':
    image_dir = Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted\part-1\norm')
    csv_path = image_dir / 'AnalysisResult.csv'
    wrong_result_save_path = image_dir / '!!!_ImagesWithWrongResult'
    analyze_dir_images(image_dir, False, csv_path, wrong_result_save_path)
