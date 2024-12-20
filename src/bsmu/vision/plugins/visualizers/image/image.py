from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Type

from bsmu.vision.plugins.visualizers import DataVisualizerPlugin, DataVisualizer

if TYPE_CHECKING:
    from bsmu.vision.plugins.settings import SettingsPlugin


class ImageVisualizerPlugin(DataVisualizerPlugin):
    def __init__(
            self, data_visualizer_cls: Type[DataVisualizer], image_visualizer_settings_plugin: SettingsPlugin = None):
        super().__init__(data_visualizer_cls, image_visualizer_settings_plugin)


class ImageVisualizer(DataVisualizer):
    pass
