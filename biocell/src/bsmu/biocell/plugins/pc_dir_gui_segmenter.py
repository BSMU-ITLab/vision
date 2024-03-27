from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSize
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from bsmu.biocell.plugins.pc_segmenter import SegmentationMode
from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.core.config import Config
from bsmu.vision.core.image.base import FlatImage
from bsmu.vision.core.plugins.base import Plugin
from bsmu.vision.core.task import DnnTask
from bsmu.vision.plugins.loaders.image.wsi import WholeSlideImageFileLoader
from bsmu.vision.plugins.windows.main import AlgorithmsMenu
from bsmu.vision.plugins.writers.image.generic import GenericImageFileWriter

if TYPE_CHECKING:
    from typing import Sequence

    from bsmu.vision.plugins.loaders.image.base import ImageFileLoader
    from bsmu.vision.plugins.storages import TaskStorage, TaskStoragePlugin
    from bsmu.vision.plugins.windows.main import MainWindow, MainWindowPlugin
    from bsmu.biocell.plugins.pc_segmenter import PcSegmenter, PcSegmenterPlugin


@dataclass
class DirSegmentationConfig(Config):
    image_dir: Path = field(default_factory=Path)
    mask_dir: Path = field(default_factory=Path)
    include_subdirs: bool = True
    overwrite_existing_masks: bool = False
    segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY


class PcDirGuiSegmenterPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'main_window_plugin': 'bsmu.vision.plugins.windows.main.MainWindowPlugin',
        'pc_segmenter_plugin': 'bsmu.biocell.plugins.pc_segmenter.PcSegmenterPlugin',
        'task_storage_plugin': 'bsmu.vision.plugins.storages.task_storage.TaskStoragePlugin',
    }

    def __init__(
            self,
            main_window_plugin: MainWindowPlugin,
            pc_segmenter_plugin: PcSegmenterPlugin,
            task_storage_plugin: TaskStoragePlugin,
    ):
        super().__init__()

        self._main_window_plugin = main_window_plugin
        self._main_window: MainWindow | None = None

        self._pc_segmenter_plugin = pc_segmenter_plugin
        self._task_storage_plugin = task_storage_plugin

        self._pc_dir_gui_segmenter: PcDirGuiSegmenter | None = None

    @property
    def pc_dir_gui_segmenter(self) -> PcDirGuiSegmenter | None:
        return self._pc_dir_gui_segmenter

    def _enable_gui(self):
        self._main_window = self._main_window_plugin.main_window

        task_storage = self._task_storage_plugin.task_storage
        # TODO: read the DirSegmentationConfig from *.conf.yaml file
        self._pc_dir_gui_segmenter = PcDirGuiSegmenter(
            DirSegmentationConfig(), self._pc_segmenter_plugin.pc_segmenter, task_storage, self._main_window)

        self._main_window.add_menu_action(
            AlgorithmsMenu,
            self.tr('Segment Cancer in Directory...'),
            self._pc_dir_gui_segmenter.segment_async_with_dialog,
        )

    def _disable(self):
        self._pc_dir_gui_segmenter = None

        self._main_window = None

        raise NotImplementedError


class DirSelector(QWidget):
    def __init__(self, title: str, default_dir: Path = None, parent: QWidget = None):
        super().__init__(parent)

        self._title = title
        self._default_dir: Path = default_dir or Path()

        self._dir_line_edit: QLineEdit | None = None
        self._browse_button: QPushButton | None = None
        self._browse_dir_row_layout: QHBoxLayout() | None = None

        self._init_gui()

    @property
    def selected_dir(self) -> Path:
        return Path(self.selected_dir_str)

    @property
    def selected_dir_str(self) -> str:
        return self._dir_line_edit.text()

    def _init_gui(self):
        title_label = QLabel(self._title)

        self._dir_line_edit = QLineEdit(str(self._default_dir.resolve()))
        self._dir_line_edit.setReadOnly(True)

        self._browse_button = QPushButton(self.tr('Browse...'))
        self._browse_button.clicked.connect(self._browse_dir)

        self._browse_dir_row_layout = QHBoxLayout()
        self._browse_dir_row_layout.addWidget(self._dir_line_edit)
        self._browse_dir_row_layout.addWidget(self._browse_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title_label)
        layout.addLayout(self._browse_dir_row_layout)
        layout.addStretch(1)

        self.setLayout(layout)
        self.adjustSize()

    def _browse_dir(self):
        selected_dir_str = QFileDialog.getExistingDirectory(self, self.tr('Select Directory'), self.selected_dir_str)
        if selected_dir_str:
            self._dir_line_edit.setText(selected_dir_str)

    def sizeHint(self) -> QSize:
        text_width = self._dir_line_edit.fontMetrics().boundingRect(self.selected_dir_str).width()
        return QSize(text_width + self._browse_dir_row_layout.spacing() + self._browse_button.width(), 0)


class DirSegmentationConfigDialog(QDialog):
    def __init__(self, config: DirSegmentationConfig, title: str, parent: QWidget = None):
        super().__init__(parent)

        self._config = config

        self.setWindowTitle(title)

        self._image_dir_selector: DirSelector | None = None
        self._mask_dir_selector: DirSelector | None = None
        self._include_subdirs_check_box: QCheckBox | None = None
        self._overwrite_existing_masks_check_box: QCheckBox | None = None
        self._segmentation_mode_combo_box: QComboBox | None = None

        self._init_gui()

    @property
    def config(self) -> DirSegmentationConfig:
        return self._config

    def _init_gui(self):
        self._image_dir_selector = DirSelector(self.tr('Images Directory:'), self._config.image_dir)
        self._mask_dir_selector = DirSelector(self.tr('Masks Directory:'), self._config.mask_dir)

        self._include_subdirs_check_box = QCheckBox(self.tr('Include Subfolders'))
        self._include_subdirs_check_box.setChecked(self._config.include_subdirs)

        self._overwrite_existing_masks_check_box = QCheckBox(self.tr('Overwrite Existing Masks'))
        self._overwrite_existing_masks_check_box.setChecked(self._config.overwrite_existing_masks)
        self._overwrite_existing_masks_check_box.setToolTip(
            self.tr('Enabling this option will overwrite any mask files with the same name as new masks.'))

        self._segmentation_mode_combo_box = QComboBox()
        for mode in SegmentationMode:
            self._segmentation_mode_combo_box.addItem(mode.display_name, mode)
        config_segmentation_mode_index = self._segmentation_mode_combo_box.findData(self._config.segmentation_mode)
        assert config_segmentation_mode_index >= 0, 'Config segmentation mode value was not found in the combo box.'
        self._segmentation_mode_combo_box.setCurrentIndex(config_segmentation_mode_index)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText(self.tr('Run Segmentation'))
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        form_layout = QFormLayout()
        form_layout.addRow(self._include_subdirs_check_box)
        form_layout.addRow(self._overwrite_existing_masks_check_box)
        form_layout.addRow(self.tr('Segmentation Mode:'), self._segmentation_mode_combo_box)

        layout = QVBoxLayout()
        layout.addWidget(self._image_dir_selector)
        layout.addWidget(self._mask_dir_selector)
        layout.addLayout(form_layout)
        layout.addStretch(1)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def accept(self):
        self._config.image_dir = self._image_dir_selector.selected_dir
        self._config.mask_dir = self._mask_dir_selector.selected_dir
        self._config.include_subdirs = self._include_subdirs_check_box.isChecked()
        self._config.overwrite_existing_masks = self._overwrite_existing_masks_check_box.isChecked()
        self._config.segmentation_mode = self._segmentation_mode_combo_box.currentData()

        super().accept()


class PcDirGuiSegmenter(QObject):
    def __init__(
            self,
            dir_segmentation_config: DirSegmentationConfig,
            pc_segmenter: PcSegmenter,
            task_storage: TaskStorage = None,
            main_window: MainWindow = None,
    ):
        super().__init__()

        self._dir_segmentation_config = dir_segmentation_config
        self._pc_segmenter = pc_segmenter
        self._task_storage = task_storage
        self._main_window = main_window

    def segment_async_with_dialog(self):
        # Pass `self._main_window` as parent to display correct window icon
        # and to place the dialog in the middle of the parent
        dir_segmentation_config_dialog = DirSegmentationConfigDialog(
            self._dir_segmentation_config, self.tr('Cancer Segmentation Settings'), self._main_window)
        dir_segmentation_config_dialog.accepted.connect(self.segment_async)
        dir_segmentation_config_dialog.open()

    def segment_async(self):
        pc_dir_segmenter = PcDirSegmenter(self._pc_segmenter, self._task_storage)
        pc_dir_segmenter.segment_async(self._dir_segmentation_config)


class PcDirSegmenter(QObject):
    def __init__(self, pc_segmenter: PcSegmenter, task_storage: TaskStorage = None):
        super().__init__()

        self._pc_segmenter = pc_segmenter
        self._task_storage = task_storage

    def segment_async(self, config: DirSegmentationConfig) -> bool:
        if (not config.image_dir.is_dir()) or (config.mask_dir.exists() and not config.mask_dir.is_dir()):
            return False

        wsi_file_loader = WholeSlideImageFileLoader()
        pc_dir_segmentation_task_name = (
            self.tr(f'PC Dir {config.segmentation_mode.short_name_with_postfix} [{config.image_dir.name}]')
        )
        pc_dir_segmentation_task = PcDirSegmentationTask(
            config, wsi_file_loader, self._pc_segmenter, pc_dir_segmentation_task_name)
        if self._task_storage is not None:
            self._task_storage.add_item(pc_dir_segmentation_task)
        ThreadPool.run_async_task(pc_dir_segmentation_task)
        return True


class PcDirSegmentationTask(DnnTask):
    def __init__(
            self,
            config: DirSegmentationConfig,
            file_loader: ImageFileLoader,
            pc_segmenter: PcSegmenter,
            name: str = '',
    ):
        super().__init__(name)

        self._config = config
        self._file_loader = file_loader
        self._pc_segmenter = pc_segmenter

        self._finished_subtask_count = 0
        self._relative_image_paths: Sequence[Path] | None = None

    def _run(self):
        return self._segment_dir_files()

    def _segment_dir_files(self):
        self._prepare_relative_image_paths()

        image_file_writer = GenericImageFileWriter()
        for self._finished_subtask_count, relative_image_path in enumerate(self._relative_image_paths):
            image_path = self._config.image_dir / relative_image_path
            file_loading_and_segmentation_task = PcFileLoadingAndSegmentationTask(
                image_path, self._file_loader, self._pc_segmenter, self._config.segmentation_mode)
            file_loading_and_segmentation_task.progress_changed.connect(
                self._on_file_loading_and_segmentation_subtask_progress_changed)
            file_loading_and_segmentation_task.run()
            mask = file_loading_and_segmentation_task.result
            mask_path = self._assemble_mask_path(relative_image_path)
            image_file_writer.write_to_file(FlatImage(mask), mask_path, mkdir=True)

    def _prepare_relative_image_paths(self):
        pattern = '**/*' if self._config.include_subdirs else '*'
        self._relative_image_paths = []
        for image_path in self._config.image_dir.glob(pattern):
            if not (image_path.is_file() and self._file_loader.can_load(image_path)):
                continue

            relative_image_path = image_path.relative_to(self._config.image_dir)
            if not self._config.overwrite_existing_masks:
                mask_path = self._assemble_mask_path(relative_image_path)
                if mask_path.exists():
                    continue

            self._relative_image_paths.append(relative_image_path)

    def _assemble_mask_path(self, relative_image_path: Path) -> Path:
        return self._config.mask_dir / relative_image_path.with_suffix('.png')

    def _on_file_loading_and_segmentation_subtask_progress_changed(self, progress: float):
        self._change_subtask_based_progress(self._finished_subtask_count, len(self._relative_image_paths), progress)


class PcFileLoadingAndSegmentationTask(DnnTask):
    def __init__(
            self,
            image_path: Path,
            image_file_loader: ImageFileLoader,
            pc_segmenter: PcSegmenter,
            segmentation_mode: SegmentationMode = SegmentationMode.HIGH_QUALITY,
            name: str = ''
    ):
        super().__init__(name)

        self._image_path = image_path
        self._image_file_loader = image_file_loader
        self._pc_segmenter = pc_segmenter
        self._segmentation_mode = segmentation_mode

    def _run(self):
        return self._load_and_segment()

    def _load_and_segment(self):
        image = self._image_file_loader.load_file(self._image_path)
        pc_segmentation_task = self._pc_segmenter.create_segmentation_task(image, self._segmentation_mode)
        pc_segmentation_task.progress_changed.connect(self.progress_changed)
        pc_segmentation_task.run()
        masks = pc_segmentation_task.result
        return self._pc_segmenter.combine_class_masks(masks)
