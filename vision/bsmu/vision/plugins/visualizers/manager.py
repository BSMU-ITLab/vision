from __future__ import annotations

from PySide2.QtCore import QObject, Signal

from bsmu.vision.app.plugin import Plugin
from bsmu.vision.core.data import Data


class DataVisualizationManagerPlugin(Plugin):
    def __init__(self, app: App):
        super().__init__(app)

        data_visualizer_registry_plugin = app.enable_plugin(
            'bsmu.vision.plugins.visualizers.registry.DataVisualizerRegistryPlugin')
        mdi_plugin = app.enable_plugin('bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin')
        self.data_visualization_manager = DataVisualizationManager(
            data_visualizer_registry_plugin.data_visualizer_registry,
            mdi_plugin.mdi)


class DataVisualizationManager(QObject):
    data_visualized = Signal(Data, list)  # (Data, List[DataViewerSubWindow])

    def __init__(self, data_visualizer_registry: DataVisualizerRegistry, mdi: Mdi):
        super().__init__()

        self.data_visualizer_registry = data_visualizer_registry
        self.mdi = mdi

    def can_visualize_data(self, data: Data) -> bool:
        return self.data_visualizer_registry.contains(type(data))

    def visualize_data(self, data: Data):
        print('Visualize data:', type(data))
        visualizer_cls = self.data_visualizer_registry.visualizer_cls(type(data))
        if visualizer_cls is not None:
            visualizer = visualizer_cls(self.mdi)
            data_viewer_sub_windows = visualizer.visualize_data(data)
            self.data_visualized.emit(data, data_viewer_sub_windows)
