from __future__ import annotations

from typing import TYPE_CHECKING

from bsmu.vision.plugins.visualizers import DataVisualizerPlugin, DataVisualizer

if TYPE_CHECKING:
    from bsmu.vision.plugins.settings import SettingsPlugin


class RasterVisualizerPlugin(DataVisualizerPlugin):
    def __init__(
            self,
            data_visualizer_cls: type[DataVisualizer],
            image_visualizer_settings_plugin: SettingsPlugin = None
    ):
        super().__init__(data_visualizer_cls, image_visualizer_settings_plugin)


class RasterVisualizer(DataVisualizer):
    pass
