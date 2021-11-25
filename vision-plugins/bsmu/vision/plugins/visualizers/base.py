from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from PySide2.QtCore import QObject, Signal

from bsmu.vision.core.plugins.processor.base import ProcessorPlugin
from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow

if TYPE_CHECKING:
    from typing import List, Type

    from bsmu.vision.core.data import Data


class DataVisualizerPlugin(ProcessorPlugin):
    def __init__(self, data_visualizer_cls: Type[DataVisualizer]):
        super().__init__(data_visualizer_cls)


class DataVisualizerMeta(abc.ABCMeta, type(QObject)):
    _DATA_TYPES = ()

    @property
    def data_types(cls) -> tuple:
        return cls._DATA_TYPES

    @property
    def processed_keys(cls) -> tuple:
        return cls.data_types


class DataVisualizer(QObject, metaclass=DataVisualizerMeta):
    data_visualized = Signal(list)  # List[DataViewerSubWindow]

    def __init__(self, mdi):
        super().__init__()

        self.mdi = mdi

    def visualize_data(self, data: Data) -> List[DataViewerSubWindow]:
        data_viewer_sub_windows = self._visualize_data(data)
        self.data_visualized.emit(data_viewer_sub_windows)
        return data_viewer_sub_windows

    @abc.abstractmethod
    def _visualize_data(self, data: Data) -> List[DataViewerSubWindow]:
        pass
