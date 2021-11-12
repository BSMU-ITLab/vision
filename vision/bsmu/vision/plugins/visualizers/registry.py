from __future__ import annotations

from bsmu.vision.core.plugin.processor import ProcessorRegistryPlugin, ProcessorRegistry
from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin


class DataVisualizerRegistryPlugin(ProcessorRegistryPlugin):
    def __init__(self):
        super().__init__(ProcessorRegistry, DataVisualizerPlugin)
