from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from bsmu.vision.core.config.united import UnitedConfig


class Settings(QObject):
    @classmethod
    def from_config(cls, config: UnitedConfig) -> Settings:
        pass
