from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

from bsmu.retinal_fundus.plugins.main_window import TableMenu
from bsmu.vision.core.models.base import ObjectParameter
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from typing import Type

    from bsmu.retinal_fundus.plugins.main_window import RetinalFundusMainWindowPlugin, RetinalFundusMainWindow
    from bsmu.retinal_fundus.plugins.table_visualizer import RetinalFundusTableVisualizerPlugin, \
        PatientRetinalFundusJournal


class PatientRetinalFundusJournalCsvExporterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.retinal_fundus.plugins.main_window.RetinalFundusMainWindowPlugin',
        'retinal_fundus_table_visualizer_plugin':
            'bsmu.retinal_fundus.plugins.table_visualizer.RetinalFundusTableVisualizerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: RetinalFundusMainWindowPlugin,
            retinal_fundus_table_visualizer_plugin: RetinalFundusTableVisualizerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: RetinalFundusMainWindow | None = None

        self._table_visualizer_plugin = retinal_fundus_table_visualizer_plugin

        self._exporter: PatientRetinalFundusJournalCsvExporter | None = None

    @property
    def exporter(self) -> PatientRetinalFundusJournalCsvExporter | None:
        return self._exporter

    def _enable(self):
        self._exporter = PatientRetinalFundusJournalCsvExporter()

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window
        self._main_window.add_menu_action(TableMenu, 'Export to Excel...', self._select_path_and_export_to_csv)

    def _select_path_and_export_to_csv(self):
        file_name, selected_filter = QFileDialog.getSaveFileName(
            parent=self._main_window, caption='Export to CSV', filter='CSV (*.csv)')
        if not file_name:
            return

        exported_parameter_types = [
            column.OBJECT_PARAMETER_TYPE
            for column in self._table_visualizer_plugin.table_visualizer.journal_viewer.columns
            if column.OBJECT_PARAMETER_TYPE is not None]
        try:
            self._exporter.export_to_csv(
                self._table_visualizer_plugin.table_visualizer.journal, exported_parameter_types, Path(file_name))
        except PermissionError:
            QMessageBox.warning(
                self._main_window,
                'File Open Error',
                'Cannot open the file due to a permission error.\n'
                'The file may be opened in another program.')

    def _disable(self):
        raise NotImplementedError


class PatientRetinalFundusJournalCsvExporter(QObject):
    IMAGE_PATH_FIELD_NAME = 'Image Path'
    IMAGE_NAME_FIELD_NAME = 'Image Name'
    DISK_AREA_FIELD_NAME = 'Disk Area'
    CUP_AREA_FIELD_NAME = 'Cup Area'
    CUP_TO_DISK_AREA_FIELD_NAME = 'Cup/Disk Area'

    def __init__(self):
        super().__init__()

    def export_to_csv(
            self,
            journal: PatientRetinalFundusJournal,
            parameter_types: list[Type[ObjectParameter]],
            csv_path: Path
    ):
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as csv_file:
            field_names = [
                self.IMAGE_PATH_FIELD_NAME,
                self.IMAGE_NAME_FIELD_NAME,
                self.DISK_AREA_FIELD_NAME,
                self.CUP_AREA_FIELD_NAME,
                self.CUP_TO_DISK_AREA_FIELD_NAME,
            ]
            additional_field_names = [parameter_type.NAME for parameter_type in parameter_types]
            field_names.extend(additional_field_names)

            writer = csv.DictWriter(csv_file, delimiter=';', fieldnames=field_names)
            writer.writeheader()

            for record in journal.records:
                record_dict = {
                    self.IMAGE_PATH_FIELD_NAME: record.image.path,
                    self.IMAGE_NAME_FIELD_NAME: record.image.path.stem,
                    self.DISK_AREA_FIELD_NAME: self.value_str_with_comma_decimal_separator(record.disk_area_str),
                    self.CUP_AREA_FIELD_NAME: self.value_str_with_comma_decimal_separator(record.cup_area_str),
                    self.CUP_TO_DISK_AREA_FIELD_NAME:
                        self.value_str_with_comma_decimal_separator(record.cup_to_disk_area_ratio_str),
                }

                for parameter_type in parameter_types:
                    record_dict[parameter_type.NAME] = \
                        self.value_str_with_comma_decimal_separator(record.parameter_value_str_by_type(parameter_type))

                writer.writerow(record_dict)

    @staticmethod
    def value_str_with_comma_decimal_separator(value_str: str) -> str:
        return value_str.replace('.', ',')
