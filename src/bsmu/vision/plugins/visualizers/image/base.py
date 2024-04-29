from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Type

from bsmu.vision.plugins.visualizers.base import DataVisualizerPlugin, DataVisualizer

if TYPE_CHECKING:
    from bsmu.vision.core.settings import Settings


class ImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(self, data_visualizer_cls: Type[DataVisualizer], image_visualizer_settings: Settings = None):
        super().__init__(data_visualizer_cls, image_visualizer_settings)


class ImageVisualizer(DataVisualizer):
    pass
