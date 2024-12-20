from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.plugins.processor import ProcessorPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.data import Data
    from bsmu.vision.core.settings import Settings
    from bsmu.vision.plugins.settings import SettingsPlugin
    from bsmu.vision.widgets.mdi.windows.data import DataViewerSubWindow


class DataVisualizerPlugin(ProcessorPlugin):
    def __init__(
            self,
            data_visualizer_cls: type[DataVisualizer],
            data_visualizer_settings_plugin: SettingsPlugin = None
    ):
        super().__init__(data_visualizer_cls, data_visualizer_settings_plugin)


class DataVisualizerMeta(type(QObject), abc.ABCMeta):
    _DATA_TYPES = ()

    @property
    def data_types(cls) -> tuple:
        return cls._DATA_TYPES

    @property
    def processed_keys(cls) -> tuple:
        return cls.data_types


class DataVisualizer(QObject, metaclass=DataVisualizerMeta):
    data_visualized = Signal(list)  # list[DataViewerSubWindow]

    def __init__(self, mdi, settings: Settings):
        super().__init__()

        self.mdi = mdi
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings

    def visualize_data(self, data: Data) -> list[DataViewerSubWindow]:
        data_viewer_sub_windows = self._visualize_data(data)
        self.data_visualized.emit(data_viewer_sub_windows)
        return data_viewer_sub_windows

    @abc.abstractmethod
    def _visualize_data(self, data: Data) -> list[DataViewerSubWindow]:
        pass
