from __future__ import annotations

from typing import TYPE_CHECKING

from PySide2.QtCore import Qt, QObject

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.bone_age.main_window import TableMenu

if TYPE_CHECKING:
    from bsmu.vision.app import App


class PatientBoneAgeJournalExporterPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        self.main_window = app.enable_plugin('bsmu.vision.plugins.windows.main.MainWindowPlugin').main_window
        self.table_visualizer = app.enable_plugin('bsmu.vision.plugins.bone_age.table_visualizer.BoneAgeTableVisualizerPlugin').table_visualizer

        self.journal_exporter = PatientBoneAgeJournalExporter(self.table_visualizer)

    def _enable(self):
        self.main_window.add_menu_action(TableMenu, 'Export', self.journal_exporter.export_to_csv)

    def _disable(self):
        self.data_visualization_manager.data_visualized.disconnect(self.table_visualizer.visualize_bone_age_data)


class PatientBoneAgeJournalExporter(QObject):
    def __init__(self, table_visualizer: BoneAgeTableVisualizer):
        super().__init__()

        self._table_visualizer = table_visualizer

    def export_to_csv(self):
        print('export to csv')
