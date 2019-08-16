from __future__ import annotations

import abc

from PySide2.QtCore import QObject, Signal

from bsmu.vision.widgets.mdi.windows.base import DataViewerSubWindow
from bsmu.vision.app.plugin import Plugin


class DataVisualizerPlugin(Plugin):
    def __init__(self, app: App, data_visualizer_cls):
        super().__init__(app)

        # self.data_visualizer_registry = app.enable_plugin(
        #     'bsmu.vision.visualizers.registry.DataVisualizerRegistryPlugin').data_visualizer_registry
        self.data_visualizer_cls = data_visualizer_cls

    # def _enable(self):
    #     self.data_visualizer_registry.register_visualizer_cls(self.data_visualizer_cls)
    #
    # def _disable(self):
    #     self.data_visualizer_registry.unregister_visualizer_cls(self.data_visualizer_cls)


class DataVisualizerMeta(abc.ABCMeta, type(QObject)):
    _DATA_TYPES = ()

    @property
    def data_types(cls) -> tuple:
        return cls._DATA_TYPES


class DataVisualizer(QObject, metaclass=DataVisualizerMeta):
    #% _DATA_TYPES = ()

    data_visualized = Signal(DataViewerSubWindow)

    def __init__(self, mdi):
        super().__init__()

        self.mdi = mdi

    @property
    def data_types(self):
        return type(self).data_types

    def visualize_data(self, data: Data):
        data_viewer_sub_window = self._visualize_data(data)
        self.data_visualized.emit(data_viewer_sub_window)
        return data_viewer_sub_window

    @abc.abstractmethod
    def _visualize_data(self, data: Data):
        pass
