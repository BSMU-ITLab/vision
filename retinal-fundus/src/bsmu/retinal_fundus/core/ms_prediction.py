from __future__ import annotations

from enum import Enum, auto

from bsmu.vision.core.models.base import ObjectParameter


class MsPredictionParameter(ObjectParameter):
    NAME = 'MS Prediction'

    @property
    def score(self) -> float | None:
        return self.value


class DiseaseStatus(Enum):
    NORM = auto()
    PATHOLOGY = auto()
    UNDEFINED = auto()

    def __str__(self):
        return self.name.capitalize()
