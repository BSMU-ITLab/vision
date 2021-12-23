from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject
from PySide2.QtWidgets import QFileDialog, QMessageBox

from bsmu.bone_age.plugins.main_window import TableMenu
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from bsmu.bone_age.plugins.main_window import BoneAgeMainWindowPlugin, BoneAgeMainWindow
    from bsmu.bone_age.plugins.table_visualizer import BoneAgeTableVisualizerPlugin, BoneAgeTableVisualizer


class PatientBoneAgeJournalExporterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.bone_age.plugins.main_window.BoneAgeMainWindowPlugin',
        'bone_age_table_visualizer_plugin':
            'bsmu.bone_age.plugins.table_visualizer.BoneAgeTableVisualizerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: BoneAgeMainWindowPlugin,
            bone_age_table_visualizer_plugin: BoneAgeTableVisualizerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: BoneAgeMainWindow | None = None

        self._bone_age_table_visualizer_plugin = bone_age_table_visualizer_plugin
        self._table_visualizer: BoneAgeTableVisualizer | None = None

        self._journal_exporter: PatientBoneAgeJournalExporter | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._table_visualizer = self._bone_age_table_visualizer_plugin.table_visualizer

        self._journal_exporter = PatientBoneAgeJournalExporter(self._table_visualizer, self._main_window)

        self._main_window.add_menu_action(TableMenu, 'Export to Excel...', self._journal_exporter.export_to_csv)

    def _disable(self):
        raise NotImplementedError


class PatientBoneAgeJournalExporter(QObject):
    IMAGE_NAME_FIELD_NAME = 'Name'
    GENDER_FIELD_NAME = 'Gender'
    BIRTHDATE_FIELD_NAME = 'Date of Birth'
    IMAGE_DATE_FIELD_NAME = 'Image Date'
    AGE_IN_IMAGE_FIELD_NAME = 'Age in Image'
    BONE_AGE_FIELD_NAME = 'Bone Age'
    AGE_DELIMITER = '//'
    HEIGHT_FIELD_NAME = 'Height'
    MAX_HEIGHT_FIELD_NAME = 'Max Height'

    DATE_STR_FORMAT = 'dd.MM.yyyy'

    def __init__(self, table_visualizer: BoneAgeTableVisualizer, main_window: BoneAgeMainWindow):
        super().__init__()

        self._table_visualizer = table_visualizer
        self._main_window = main_window

    def export_to_csv(self):
        file_name, selected_filter = QFileDialog.getSaveFileName(
            parent=self._main_window, caption='Export to CSV', filter='CSV (*.csv)')
        if not file_name:
            return

        try:
            csv_file = open(file_name, 'w', encoding='utf-8-sig', newline='')
        except PermissionError:
            QMessageBox.warning(self._main_window, 'File Open Error',
                                'Cannot open the file due to a permission error.\n'
                                'The file may be opened in another program.')
        else:
            with csv_file:
                age_in_image_with_format_field_name = \
                    f'{self.AGE_IN_IMAGE_FIELD_NAME} ({self._table_visualizer.age_format.ABBR})'
                bone_age_with_format_field_name = \
                    f'{self.BONE_AGE_FIELD_NAME} ({self._table_visualizer.age_format.ABBR})'
                field_names = [self.IMAGE_NAME_FIELD_NAME, self.GENDER_FIELD_NAME, self.BIRTHDATE_FIELD_NAME,
                               self.IMAGE_DATE_FIELD_NAME, age_in_image_with_format_field_name,
                               bone_age_with_format_field_name, self.HEIGHT_FIELD_NAME, self.MAX_HEIGHT_FIELD_NAME]

                writer = csv.DictWriter(csv_file, delimiter=';', fieldnames=field_names)
                writer.writeheader()

                for record in self._table_visualizer.journal.records:
                    writer.writerow({self.IMAGE_NAME_FIELD_NAME: record.image.path.stem,
                                     self.GENDER_FIELD_NAME: 'Man' if record.male else 'Woman',
                                     self.BIRTHDATE_FIELD_NAME: record.birthdate.toString(self.DATE_STR_FORMAT),
                                     self.IMAGE_DATE_FIELD_NAME: record.image_date.toString(self.DATE_STR_FORMAT),
                                     age_in_image_with_format_field_name: self._table_visualizer.age_format.format(
                                         record.age_in_image, delimiter=self.AGE_DELIMITER),
                                     bone_age_with_format_field_name: self._table_visualizer.age_format.format(
                                         record.bone_age, delimiter=self.AGE_DELIMITER),
                                     self.HEIGHT_FIELD_NAME: record.height_str,
                                     self.MAX_HEIGHT_FIELD_NAME: record.max_height_str,
                                     })
