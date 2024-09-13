from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from bsmu.vision.core.palette import Palette
from bsmu.vision.core.settings import Settings
from bsmu.vision.plugins.settings import SettingsPlugin

if TYPE_CHECKING:
    from bsmu.vision.core.config import UnitedConfig
    from bsmu.vision.plugins.windows.main import MainWindowPlugin


class PalettePackSettingsPlugin(SettingsPlugin):
    def __init__(self, main_window_plugin: MainWindowPlugin):
        super().__init__(main_window_plugin, PalettePackSettings)

    @property
    def settings(self) -> PalettePackSettings:
        return cast(PalettePackSettings, self._settings)


class PalettePackSettings(Settings):
    def __init__(self, main_palette: Palette):
        super().__init__()

        self._main_palette = main_palette

    @property
    def main_palette(self) -> Palette:
        return self._main_palette

    @classmethod
    def from_config(cls, config: UnitedConfig) -> PalettePackSettings:
        return cls(Palette.from_config(config.value('main_palette')))
