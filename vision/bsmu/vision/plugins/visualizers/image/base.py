from __future__ import annotations

from typing import Type

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer


class ImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, data_visualizer_cls: Type[DataVisualizer]):
        super().__init__(data_visualizer_cls)


class ImageVisualizer(DataVisualizer):
    pass
