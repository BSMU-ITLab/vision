from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QEvent

from bsmu.vision.core.plugins import Plugin

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

    from bsmu.vision.core.data import Data
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.visualizers.manager import DataVisualizationManagerPlugin, DataVisualizationManager
    from bsmu.vision.plugins.readers.manager import FileReadingManagerPlugin, FileReadingManager
    from bsmu.vision.plugins.postread.manager import (
        PostReadConversionManagerPlugin, PostReadConversionManager)


class FileDropperPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
        'file_reading_manager_plugin': 'bsmu.vision.plugins.readers.manager.FileReadingManagerPlugin',
        'post_read_conversion_manager_plugin':
            'bsmu.vision.plugins.postread.manager.PostReadConversionManagerPlugin',
        'data_visualization_manager_plugin': 'bsmu.vision.plugins.visualizers.manager.DataVisualizationManagerPlugin',
    }

    def __init__(
            self,
            mdi_plugin: MdiPlugin,
            file_reading_manager_plugin: FileReadingManagerPlugin,
            post_read_conversion_manager_plugin: PostReadConversionManagerPlugin,
            data_visualization_manager_plugin: DataVisualizationManagerPlugin,
    ):
        super().__init__()

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._file_reading_manager_plugin = file_reading_manager_plugin
        self._file_reading_manager: FileReadingManager | None = None

        self._post_read_conversion_manager_plugin = post_read_conversion_manager_plugin
        self._post_read_conversion_manager: PostReadConversionManager | None = None

        self._data_visualization_manager_plugin = data_visualization_manager_plugin
        self._data_visualization_manager: DataVisualizationManager | None = None

        self._file_dropper: FileDropper | None = None

    @property
    def file_dropper(self) -> FileDropper:
        return self._file_dropper

    def _enable(self):
        self._mdi = self._mdi_plugin.mdi
        self._file_reading_manager = self._file_reading_manager_plugin.file_reading_manager
        self._post_read_conversion_manager = self._post_read_conversion_manager_plugin.post_read_conversion_manager
        self._data_visualization_manager = self._data_visualization_manager_plugin.data_visualization_manager

        self._file_dropper = FileDropper(
            self._file_reading_manager,
            self._post_read_conversion_manager,
            self._data_visualization_manager,
        )

        self._mdi.setAcceptDrops(True)
        self._mdi.installEventFilter(self._file_dropper)

    def _disable(self):
        self._mdi.removeEventFilter(self._file_dropper)

        self._file_dropper = None


class FileDropper(QObject):
    def __init__(self, file_reading_manager: FileReadingManager,
                 post_read_conversion_manager: PostReadConversionManager,
                 visualization_manager: DataVisualizationManager):
        super().__init__()

        self.file_reading_manager = file_reading_manager
        self.post_read_conversion_manager = post_read_conversion_manager
        self.visualization_manager = visualization_manager

        self.dragged_readable_file_paths = []

    def eventFilter(self, watched_obj: QObject, event: QEvent):
        if event.type() == QEvent.DragEnter:
            self._on_drag_enter(event)
            return True
        elif event.type() == QEvent.Drop:
            self._on_drop(event)
            return True
        else:
            return super().eventFilter(watched_obj, event)

    def _on_drag_enter(self, event: QDragEnterEvent):
        self.dragged_readable_file_paths.clear()

        mime_data = event.mimeData()
        for url in mime_data.urls():
            file_path = Path(url.toLocalFile())
            if self.file_reading_manager.can_read_file(file_path):
                self.dragged_readable_file_paths.append(file_path)

        event.setAccepted(bool(self.dragged_readable_file_paths))

    def _on_drop(self, event: QDropEvent):
        logging.info(f'Drop: {self.dragged_readable_file_paths}')
        for file_path in self.dragged_readable_file_paths:
            file_reading_task = self.file_reading_manager.read_file_async_and_add_task_into_task_storage(file_path)
            file_reading_task.on_finished = self._on_file_read

    def _on_file_read(self, data: Data | None):
        data = self.post_read_conversion_manager.convert_data(data)
        self.visualization_manager.visualize_data(data)
