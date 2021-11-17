from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide2.QtCore import QObject, Qt
from ruamel.yaml import YAML
from sortedcontainers import SortedDict

from bsmu.vision.core import date
from bsmu.vision.core.image.layered import LayeredImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.plugins.bone_age.main_window import AtlasMenu
from bsmu.vision.plugins.bone_age.table_visualizer import PatientBoneAgeRecordAction
from bsmu.vision.plugins.windows.main import WindowsMenu
from bsmu.vision.widgets.mdi.windows.image.layered import LayeredImageViewerSubWindow
from bsmu.vision.widgets.viewers.image.layered.flat import LayeredFlatImageViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.bone_age.main_window import BoneAgeMainWindowPlugin, BoneAgeMainWindow
    from bsmu.vision.plugins.bone_age.table_visualizer import BoneAgeTableVisualizerPlugin, BoneAgeTableVisualizer, \
        PatientBoneAgeRecord
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.loaders.manager import FileLoadingManagerPlugin, FileLoadingManager


class BoneAgeAtlasVisualizerPlugin(Plugin):
    DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.bone_age.main_window.BoneAgeMainWindowPlugin',
        'bone_age_table_visualizer_plugin':
            'bsmu.vision.plugins.bone_age.table_visualizer.BoneAgeTableVisualizerPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_loading_manager_plugin': 'bsmu.vision.plugins.loaders.manager.FileLoadingManagerPlugin',
    }

    def __init__(
            self,
            main_window_plugin: BoneAgeMainWindowPlugin,
            bone_age_table_visualizer_plugin: BoneAgeTableVisualizerPlugin,
            mdi_plugin: MdiPlugin,
            file_loading_manager_plugin: FileLoadingManagerPlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: BoneAgeMainWindow | None = None

        self._bone_age_table_visualizer_plugin = bone_age_table_visualizer_plugin
        self._bone_age_table_visualizer: BoneAgeTableVisualizer | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_loading_manager_plugin = file_loading_manager_plugin

        self._bone_age_atlas_visualizer: BoneAgeAtlasVisualizer | None = None
        self._show_atlas_action: PatientBoneAgeRecordAction | None = None

    def _enable(self):
        self._main_window = self._main_window_plugin.main_window
        self._bone_age_table_visualizer = self._bone_age_table_visualizer_plugin.table_visualizer
        self._mdi = self._mdi_plugin.mdi

        self._bone_age_atlas_visualizer = BoneAgeAtlasVisualizer(
            self._mdi, self._file_loading_manager_plugin.file_loading_manager, self._bone_age_table_visualizer)

        self._show_atlas_action = PatientBoneAgeRecordAction('Show Atlas')
        self._show_atlas_action.triggered_on_record.connect(self._bone_age_atlas_visualizer.show_atlas_for_record)
        self._bone_age_table_visualizer.add_age_column_context_menu_action(self._show_atlas_action)

        self._main_window.add_menu_action(
            WindowsMenu, 'Atlas', self._bone_age_atlas_visualizer.raise_atlas_sub_windows, Qt.CTRL + Qt.Key_2)

        self._main_window.add_menu_action(
            AtlasMenu, 'Next Image', self._bone_age_atlas_visualizer.show_next_image, Qt.CTRL + Qt.Key_Up)
        self._main_window.add_menu_action(
            AtlasMenu, 'Previous Image', self._bone_age_atlas_visualizer.show_prev_image, Qt.CTRL + Qt.Key_Down)

    def _disable(self):
        self._bone_age_table_visualizer.remove_age_column_context_menu_action(self._show_atlas_action)
        self._show_atlas_action.triggered_on_record.disconnect(self._bone_age_atlas_visualizer.show_atlas_for_record)
        self._show_atlas_action = None

        self._bone_age_atlas_visualizer = None

        raise NotImplementedError


class BoneAgeAtlasVisualizer(QObject):
    _ATLAS_DIR = Path(__file__).parent / 'greulich-pyle-atlas'
    _ATLAS_INDEX_FILE_NAME = 'autogen-index.yaml'

    _ATLAS_FILE_NAME_PATTERN_STR = r'(?P<years>\d*)-(?P<months>\d*)\.png'

    def __init__(self, mdi: Mdi, file_loading_manager: FileLoadingManager, table_visualizer: BoneAgeTableVisualizer):
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

        self._cur_gender_sorted_atlas_image_key_index = None  # Atlas key index of current displayed image
        self._cur_gender_sorted_atlas_index = None
        self._cur_atlas_is_male = None

        self._atlas_sub_windows = None

    def raise_atlas_sub_windows(self):
        if self._atlas_sub_windows is None:
            return

        # This will take the focus off from the table sub window,
        # else this will raise later table over the atlas sub windows.
        self.mdi.setActiveSubWindow(self._atlas_sub_windows[0])

        for atlas_sub_window in self._atlas_sub_windows:
            atlas_sub_window.show_normal()

            atlas_sub_window.raise_()

    def show_atlas_for_record(self, record: PatientBoneAgeRecord):
        self._cur_atlas_is_male = record.male

        self._cur_gender_sorted_atlas_index = self._genders_sorted_atlas_indexes.get(record.male)
        if self._cur_gender_sorted_atlas_index is None:
            self._cur_gender_sorted_atlas_index = SortedDict(self._read_gender_atlas_index_file(record.male))
            self._genders_sorted_atlas_indexes[record.male] = self._cur_gender_sorted_atlas_index

        # Find the two closest key indexes around the |record.bone_age|
        right_key_index = self._cur_gender_sorted_atlas_index.bisect_right(record.bone_age)
        left_key_index = right_key_index - 1
        # Find key index with the closest value to |record.bone_age|
        gender_sorted_atlas_index_keys = self._cur_gender_sorted_atlas_index.keys()
        right_key = gender_sorted_atlas_index_keys[right_key_index] \
            if right_key_index < len(gender_sorted_atlas_index_keys) else float('-inf')
        left_key = gender_sorted_atlas_index_keys[left_key_index] \
            if left_key_index < len(gender_sorted_atlas_index_keys) else float('-inf')

        # Find the atlas nearest key index to the record bone age
        self._cur_gender_sorted_atlas_image_key_index = right_key_index \
            if abs(right_key - record.bone_age) < abs(left_key - record.bone_age) \
            else left_key_index

        if self._atlas_sub_windows is None:
            self._create_atlas_sub_windows()

        self._show_atlas_image_set()

    def _show_atlas_image_set(self):
        self._show_atlas_image_by_key_index(
            self._cur_gender_sorted_atlas_index, self._cur_gender_sorted_atlas_image_key_index,
            self._cur_atlas_is_male, self._atlas_sub_windows[0])
        self._show_atlas_image_by_key_index(
            self._cur_gender_sorted_atlas_index, self._cur_gender_sorted_atlas_image_key_index + 1,
            self._cur_atlas_is_male, self._atlas_sub_windows[1])
        self._show_atlas_image_by_key_index(
            self._cur_gender_sorted_atlas_index, self._cur_gender_sorted_atlas_image_key_index - 1,
            self._cur_atlas_is_male, self._atlas_sub_windows[2])

        self.raise_atlas_sub_windows()

    def _create_atlas_sub_windows(self):
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

        self._atlas_sub_windows = 3 * [None]
        self._atlas_sub_windows[0] = self._create_atlas_sub_window(nearest_atlas_image_layout_anchors)
        self._atlas_sub_windows[1] = self._create_atlas_sub_window(next_atlas_image_layout_anchors)
        self._atlas_sub_windows[2] = self._create_atlas_sub_window(prev_atlas_image_layout_anchors)

    def show_next_image(self):
        if self._cur_gender_sorted_atlas_image_key_index is None:
            return

        if self._cur_gender_sorted_atlas_image_key_index < len(self._cur_gender_sorted_atlas_index) - 2:
            self._cur_gender_sorted_atlas_image_key_index += 1

            self._show_atlas_image_set()

    def show_prev_image(self):
        if self._cur_gender_sorted_atlas_image_key_index is None:
            return

        if self._cur_gender_sorted_atlas_image_key_index > 1:
            self._cur_gender_sorted_atlas_image_key_index -= 1

            self._show_atlas_image_set()

    def _show_atlas_image_by_key_index(
            self, sorted_atlas_index: SortedDict, key_index, male: bool, atlas_sub_window: LayeredImageViewerSubWindow):
        if key_index < 0 or key_index >= len(sorted_atlas_index.keys()):
            return

        # key = sorted_atlas_index_keys[key_index]
        # atlas_image_file_name = sorted_atlas_index[key]
        atlas_image_file_name = sorted_atlas_index.values()[key_index]
        atlas_image_file_path = self._GENDERS_ATLAS_DIRS[male] / atlas_image_file_name

        atlas_image = self.file_loading_manager.load_file(atlas_image_file_path)
        atlas_sub_window.viewer.layers[0].image = atlas_image

    def _create_atlas_sub_window(self, atlas_sub_window_anchors: np.ndarray) -> LayeredImageViewerSubWindow:
        atlas_layered_image = LayeredImage()
        atlas_layered_image.add_layer_from_image(None)
        atlas_image_viewer = LayeredFlatImageViewer(atlas_layered_image)
        atlas_sub_window = LayeredImageViewerSubWindow(atlas_image_viewer)
        atlas_image_viewer.data_name_changed.connect(atlas_sub_window.setWindowTitle)
        self.mdi.addSubWindow(atlas_sub_window)

        atlas_sub_window.layout_anchors = atlas_sub_window_anchors
        atlas_sub_window.lay_out_to_anchors()
        atlas_sub_window.show()

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
