from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.bone_age.table_visualizer import BoneAgeTableVisualizerPlugin, PatientBoneAgeRecord, \
    PatienBoneAgeRecordAction

if TYPE_CHECKING:
    from bsmu.vision.app import App


class BoneAgeAtlasVisualizerPlugin(Plugin):
    def __init__(self, app: App,
                 bone_age_table_visualizer_plugin=BoneAgeTableVisualizerPlugin.full_name()):
        super().__init__(app)

        self.bone_age_table_visualizer = app.enable_plugin(bone_age_table_visualizer_plugin).table_visualizer

        self._show_atlas_action = PatienBoneAgeRecordAction('Show Atlas')
        self._show_atlas_action.triggered_on_record.connect(self._show_atlas)

    def _enable(self):
        self.bone_age_table_visualizer.add_age_column_context_menu_action(self._show_atlas_action)

    def _disable(self):
        self.bone_age_table_visualizer.remove_age_column_context_menu_action(self._show_atlas_action)

    def _show_atlas(self, record: PatientBoneAgeRecord):
        print('SHOW ATLAS!!!', record.bone_age)
