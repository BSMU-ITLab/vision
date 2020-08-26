from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject
from PySide2.QtWidgets import QFileDialog

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.bone_age.main_window import TableMenu
from bsmu.vision.plugins.bone_age.table_visualizer import YearsMonthsAgeFormat

if TYPE_CHECKING:
    from bsmu.vision.app import App


class PatientBoneAgeJournalExporterPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.table_visualizer = app.enable_plugin('bsmu.vision.plugins.bone_age.table_visualizer.BoneAgeTableVisualizerPlugin').table_visualizer

        self.journal_exporter = PatientBoneAgeJournalExporter(self.table_visualizer)

    def _enable(self):
        self.main_window.add_menu_action(TableMenu, 'Export to CSV...', self.journal_exporter.export_to_csv)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.table_visualizer.visualize_bone_age_data)


class PatientBoneAgeJournalExporter(QObject):
    IMAGE_NAME_FIELD_NAME = 'Name'
    GENDER_FIELD_NAME = 'Gender'
    BIRTHDATE_FIELD_NAME = 'Date of Birth'
    IMAGE_DATE_FIELD_NAME = 'Image Date'
    AGE_IN_IMAGE_FIELD_NAME = 'Age in Image (Y // M)'
    BONE_AGE_FIELD_NAME = 'Bone Age (Y // M)'
    AGE_DELIMITER = '//'

    DATE_STR_FORMAT = 'dd.MM.yyyy'

    def __init__(self, table_visualizer: BoneAgeTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

    def export_to_csv(self):
        file_name, selected_filter = QFileDialog.getSaveFileName(caption='Export to CSV', filter='CSV (*.csv)')
        if not file_name:
            return

        with open(file_name, 'w', newline='') as csv_file:
            field_names = [self.IMAGE_NAME_FIELD_NAME, self.GENDER_FIELD_NAME, self.BIRTHDATE_FIELD_NAME,
                           self.IMAGE_DATE_FIELD_NAME, self.AGE_IN_IMAGE_FIELD_NAME, self.BONE_AGE_FIELD_NAME]

            writer = csv.DictWriter(csv_file, delimiter=';', fieldnames=field_names)
            writer.writeheader()

            for record in self._table_visualizer.journal.records:
                writer.writerow({self.IMAGE_NAME_FIELD_NAME: record.image.path.stem,
                                 self.GENDER_FIELD_NAME: 'Man' if record.male else 'Woman',
                                 self.BIRTHDATE_FIELD_NAME: record.birthdate.toString(self.DATE_STR_FORMAT),
                                 self.IMAGE_DATE_FIELD_NAME: record.image_date.toString(self.DATE_STR_FORMAT),
                                 self.AGE_IN_IMAGE_FIELD_NAME: YearsMonthsAgeFormat.format(
                                     record.age_in_image, delimiter=self.AGE_DELIMITER),
                                 self.BONE_AGE_FIELD_NAME: YearsMonthsAgeFormat.format(
                                     record.bone_age, delimiter=self.AGE_DELIMITER),
                                 })
