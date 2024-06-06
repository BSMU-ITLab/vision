from dataclasses import dataclass

from bsmu.vision.core.config import Config


@dataclass
class Visibility(Config):
    visible: bool = True
    opacity: float = 1
