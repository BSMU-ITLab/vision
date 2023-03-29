from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from bsmu.vision.core.data import Data
from bsmu.vision.core.plugins.base import Plugin

if TYPE_CHECKING:
    from bsmu.vision.core.plugins.processor.registry import ProcessorRegistry
    from bsmu.vision.plugins.doc_interfaces.mdi import MdiPlugin, Mdi
    from bsmu.vision.plugins.visualizers.registry import DataVisualizerRegistryPlugin


class DataVisualizationManagerPlugin(Plugin):
    _DEFAULT_DEPENDENCY_PLUGIN_FULL_NAME_BY_KEY = {
        'data_visualizer_registry_plugin': 'bsmu.vision.plugins.visualizers.registry.DataVisualizerRegistryPlugin',
        'mdi_plugin': 'bsmu.vision.plugins.doc_interfaces.mdi.MdiPlugin',
    }

    def __init__(
            self,
            data_visualizer_registry_plugin: DataVisualizerRegistryPlugin,
            mdi_plugin: MdiPlugin):
        super().__init__()

        self._data_visualizer_registry_plugin = data_visualizer_registry_plugin
        self._data_visualizer_registry: ProcessorRegistry | None = None

        self._mdi_plugin = mdi_plugin
        self._mdi: Mdi | None = None

        self._data_visualization_manager: DataVisualizationManager | None = None

    @property
    def data_visualization_manager(self) -> DataVisualizationManager | None:
        return self._data_visualization_manager

    def _enable(self):
        self._data_visualizer_registry = self._data_visualizer_registry_plugin.processor_registry
        self._mdi = self._mdi_plugin.mdi

        self._data_visualization_manager = DataVisualizationManager(self._data_visualizer_registry, self._mdi)

    def _disable(self):
        self._data_visualization_manager = None


class DataVisualizationManager(QObject):
    data_visualized = Signal(Data, list)  # (Data, List[DataViewerSubWindow])

    def __init__(self, data_visualizer_registry: ProcessorRegistry, mdi: Mdi):
        super().__init__()

        self.data_visualizer_registry = data_visualizer_registry
        self.mdi = mdi

    def can_visualize_data(self, data: Data) -> bool:
        return self.data_visualizer_registry.contains(type(data))

    def visualize_data(self, data: Data):
        logging.info(f'Visualize data: {type(data)}')
        visualizer_cls_with_settings = self.data_visualizer_registry.processor_cls_with_settings(type(data))
        if visualizer_cls_with_settings is not None:
            visualizer = visualizer_cls_with_settings.processor_cls(
                self.mdi, visualizer_cls_with_settings.processor_settings)
            data_viewer_sub_windows = visualizer.visualize_data(data)
            self.data_visualized.emit(data, data_viewer_sub_windows)
