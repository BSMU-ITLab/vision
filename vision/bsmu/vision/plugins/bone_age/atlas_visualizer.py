from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject, Qt
from ruamel.yaml import YAML
from sortedcontainers import SortedDict

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.plugins.bone_age.table_visualizer import BoneAgeTableVisualizerPlugin, PatientBoneAgeRecord, \
    PatienBoneAgeRecordAction
from bsmu.vision_core import date

if TYPE_CHECKING:
    from bsmu.vision.app import App
from typing import Union
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer
from bsmu.vision_core.image.layered import LayeredImage
from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin
from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin
from bsmu.vision.plugins.bone_age.main_window import BoneAgeMainWindowPlugin, AtlasMenu
from bsmu.vision.plugins.windows.main import WindowsMenu, MainWindowPlugin


class BoneAgeAtlasVisualizerPlugin(Plugin):
    def __init__(self, app: App,
                 main_window_plugin=MainWindowPlugin.full_name(),   ## BoneAgeMainWindowPlugin.full_name(),
                 bone_age_table_visualizer_plugin=BoneAgeTableVisualizerPlugin.full_name(),
                 mdi_plugin: Union[str, MdiPlugin] = MdiPlugin.full_name(),
                 file_loading_manager_plugin: Union[str, FileLoadingManagerPlugin] = FileLoadingManagerPlugin.full_name(),
                 ):
        super().__init__(app)

        self.main_window = app.enable_plugin(main_window_plugin).main_window
        self.bone_age_table_visualizer = app.enable_plugin(bone_age_table_visualizer_plugin).table_visualizer
        mdi = app.enable_plugin(mdi_plugin).mdi
        file_loading_manager = app.enable_plugin(file_loading_manager_plugin).file_loading_manager

        self.bone_age_atlas_visualizer = BoneAgeAtlasVisualizer(mdi, file_loading_manager,
                                                                self.bone_age_table_visualizer)

        self._show_atlas_action = PatienBoneAgeRecordAction('Show Atlas')
        self._show_atlas_action.triggered_on_record.connect(self.bone_age_atlas_visualizer.show_atlas_for_record)

    def _enable(self):
        self.bone_age_table_visualizer.add_age_column_context_menu_action(self._show_atlas_action)

        self.main_window.add_menu_action(WindowsMenu, 'Atlas', self.bone_age_atlas_visualizer.raise_atlas_sub_windows,
                                         Qt.CTRL + Qt.Key_2)

        self.main_window.add_menu_action(AtlasMenu, 'Next Image', self.bone_age_atlas_visualizer.show_next_image,
                                         Qt.CTRL + Qt.Key_Up)
        self.main_window.add_menu_action(AtlasMenu, 'Previous Image', self.bone_age_atlas_visualizer.show_prev_image,
                                         Qt.CTRL + Qt.Key_Down)

    def _disable(self):
        self.bone_age_table_visualizer.remove_age_column_context_menu_action(self._show_atlas_action)


class BoneAgeAtlasVisualizer(QObject):
    _ATLAS_DIR = Path(__file__).parent / 'greulich-pyle-atlas'
    _ATLAS_INDEX_FILE_NAME = 'autogen-index.yaml'

    _ATLAS_FILE_NAME_PATTERN_STR = r'(?P<years>\d*)-(?P<months>\d*)\.png'

    def __init__(self, mdi: Mdi, file_loading_manager: FileLoadingManager,
                 table_visualizer: BoneAgeTableVisualizer):
        super().__init__()

        self.mdi = mdi
        self.file_loading_manager = file_loading_manager
        self.table_visualizer = table_visualizer

        self._ATLAS_FILE_NAME_PATTERN = re.compile(self._ATLAS_FILE_NAME_PATTERN_STR)

        self._GENDERS_ATLAS_DIR_NAMES = {True: 'man',
                                         False: 'woman'}
        self._GENDERS_ATLAS_DIRS = {male: self._ATLAS_DIR / gender_dir_name for (male, gender_dir_name)
                                    in self._GENDERS_ATLAS_DIR_NAMES.items()}
        self._GENDERS_ATLAS_INDEX_FILE_PATHS = {male: gender_atlas_dir / self._ATLAS_INDEX_FILE_NAME
                                                for (male, gender_atlas_dir) in self._GENDERS_ATLAS_DIRS.items()}

        for gender_atlas_index_file_path in self._GENDERS_ATLAS_INDEX_FILE_PATHS.values():
            self._generate_atlas_index_file(gender_atlas_index_file_path)

        self._genders_sorted_atlas_indexes = {}  # Male: sorted atlas indexes

        # self.nearest_key_index
        # sorted_atlas_index

        self._nearest_atlas_sub_window = None
        self._next_atlas_sub_window = None
        self._prev_atlas_sub_window = None

    def raise_atlas_sub_windows(self):
        if self._nearest_atlas_sub_window is None:
            return

        # This will take the focus off from the table sub window,
        # else this will raise later table over the atlas sub windows.
        self.mdi.setActiveSubWindow(self._nearest_atlas_sub_window)

        self._nearest_atlas_sub_window.raise_()
        self._next_atlas_sub_window.raise_()
        self._prev_atlas_sub_window.raise_()

    def show_atlas_for_record(self, record: PatientBoneAgeRecord):
        gender_sorted_atlas_index = self._genders_sorted_atlas_indexes.get(record.male)
        if gender_sorted_atlas_index is None:
            gender_sorted_atlas_index = SortedDict(self._read_gender_atlas_index_file(record.male))
            self._genders_sorted_atlas_indexes[record.male] = gender_sorted_atlas_index

        # Find the two closest key indexes around the |record.bone_age|
        right_key_index = gender_sorted_atlas_index.bisect_right(record.bone_age)
        left_key_index = right_key_index - 1
        # Find key index with the closest value to |record.bone_age|
        gender_sorted_atlas_index_keys = gender_sorted_atlas_index.keys()
        right_key = gender_sorted_atlas_index_keys[right_key_index] \
            if right_key_index < len(gender_sorted_atlas_index_keys) else float('-inf')
        left_key = gender_sorted_atlas_index_keys[left_key_index] \
            if left_key_index < len(gender_sorted_atlas_index_keys) else float('-inf')

        self.nearest_key_index = right_key_index \
            if abs(right_key - record.bone_age) < abs(left_key - record.bone_age) \
            else left_key_index

        table_sub_window_layout_anchors = self.table_visualizer.journal_sub_window.layout_anchors
        table_mid_x_anchor = 0.4 * (table_sub_window_layout_anchors[1, 0] - table_sub_window_layout_anchors[0, 0]) \
                             + table_sub_window_layout_anchors[0, 0]
        table_mid_y_anchor = 0.5 * (table_sub_window_layout_anchors[1, 1] - table_sub_window_layout_anchors[0, 1]) \
                             + table_sub_window_layout_anchors[0, 1]
        nearest_atlas_image_layout_anchors = np.copy(table_sub_window_layout_anchors)
        nearest_atlas_image_layout_anchors[0, 0] = table_mid_x_anchor

        next_atlas_image_layout_anchors = np.copy(table_sub_window_layout_anchors)
        next_atlas_image_layout_anchors[1, 0] = table_mid_x_anchor
        next_atlas_image_layout_anchors[1, 1] = table_mid_y_anchor

        prev_atlas_image_layout_anchors = np.copy(table_sub_window_layout_anchors)
        prev_atlas_image_layout_anchors[1, 0] = table_mid_x_anchor
        prev_atlas_image_layout_anchors[0, 1] = table_mid_y_anchor

        self._nearest_atlas_sub_window = self._show_atlas_image_by_key_index(
            gender_sorted_atlas_index, nearest_key_index, record.male, self._nearest_atlas_sub_window,
            nearest_atlas_image_layout_anchors)
        self._next_atlas_sub_window = self._show_atlas_image_by_key_index(
            gender_sorted_atlas_index, nearest_key_index + 1, record.male, self._next_atlas_sub_window,
            next_atlas_image_layout_anchors)
        self._prev_atlas_sub_window = self._show_atlas_image_by_key_index(
            gender_sorted_atlas_index, nearest_key_index - 1, record.male, self._prev_atlas_sub_window,
            prev_atlas_image_layout_anchors)

        self.raise_atlas_sub_windows()

    def show_next_image(self):
        ...

    def show_prev_image(self):
        ...

    def _show_atlas_image_by_key_index(
            self, sorted_atlas_index: SortedDict, key_index, male: bool, atlas_sub_window: LayeredImageViewerSubWindow,
            atlas_sub_window_anchors: np.ndarray) -> LayeredImageViewerSubWindow:
        if key_index < 0 or key_index >= len(sorted_atlas_index.keys()):
            return

        # key = sorted_atlas_index_keys[key_index]
        # atlas_image_file_name = sorted_atlas_index[key]
        atlas_image_file_name = sorted_atlas_index.values()[key_index]
        atlas_image_file_path = self._GENDERS_ATLAS_DIRS[male] / atlas_image_file_name

        atlas_image = self.file_loading_manager.load_file(atlas_image_file_path)

        if atlas_sub_window is None:
            atlas_sub_window = self._create_atlas_sub_window(atlas_image)
            atlas_sub_window.layout_anchors = atlas_sub_window_anchors
            atlas_sub_window.lay_out_to_anchors()
            atlas_sub_window.show()

        atlas_sub_window.viewer.layers[0].image = atlas_image
        return atlas_sub_window

    def _create_atlas_sub_window(self, atlas_image: Image) -> LayeredImageViewerSubWindow:
        atlas_layered_image = LayeredImage()
        atlas_layered_image.add_layer_from_image(atlas_image)
        atlas_image_viewer = LayeredFlatImageViewer(atlas_layered_image)
        atlas_sub_window = LayeredImageViewerSubWindow(atlas_image_viewer)
        atlas_image_viewer.data_name_changed.connect(atlas_sub_window.setWindowTitle)
        self.mdi.addSubWindow(atlas_sub_window)
        return atlas_sub_window

    def _generate_atlas_index_file(self, atlas_index_file_path: Path):
        if atlas_index_file_path.exists():
            # Do no overwrite the index file, if it exists
            return

        atlas_index = dict()
        for atlas_file_path in atlas_index_file_path.parent.glob('*.png'):
            match = self._ATLAS_FILE_NAME_PATTERN.match(atlas_file_path.name)
            years = int(match.group('years'))
            months = int(match.group('months'))

            days = date.years_months_to_days(years, months)
            atlas_index[days] = atlas_file_path.name

        yaml = YAML()
        with open(str(atlas_index_file_path), 'w') as atlas_index_file:
            yaml.dump(atlas_index, atlas_index_file)

    def _read_gender_atlas_index_file(self, male: bool) -> dict:
        gender_atlas_index_file_path = self._GENDERS_ATLAS_INDEX_FILE_PATHS[male]
        yaml = YAML()
        with open(gender_atlas_index_file_path) as atlas_index_file:
            return dict(yaml.load(atlas_index_file))
