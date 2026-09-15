from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bsmu.vision.core.data.tiled_backend import TiledBackend


_MIN_EPS = 1e-9
_LEVEL_HYSTERESIS_MARGIN = 0.10


class LevelSelectionMode(Enum):
    BALANCED = auto()
    SHARP = auto()


class LevelSelector(ABC):
    """Base strategy for selecting the optimal zoom level."""

    def __init__(self, hysteresis_margin: float = _LEVEL_HYSTERESIS_MARGIN) -> None:
        self._hysteresis_margin = hysteresis_margin

    @property
    def hysteresis_margin(self) -> float:
        return self._hysteresis_margin

    def resolve_level(
            self,
            tiled_backend: TiledBackend,
            target_ds: float,
            current_level: int | None,
    ) -> int:
        """Determine the optimal level based on target downsample and current state."""
        if tiled_backend.level_count == 0:
            return 0

        candidate = self.best_level(tiled_backend, target_ds)

        if current_level is None or not (0 <= current_level < tiled_backend.level_count):
            return candidate

        if candidate == current_level:
            return current_level

        # Immediate switch if the jump is more than 1 level to avoid lag
        if abs(candidate - current_level) > 1:
            return candidate

        return self._resolve_adjacent_hysteresis(
            tiled_backend, current_level, candidate, target_ds,
        )

    @abstractmethod
    def best_level(self, tiled_backend: TiledBackend, target_ds: float) -> int:
        """Return the best level ignoring current level and hysteresis."""
        raise NotImplementedError

    @abstractmethod
    def _resolve_adjacent_hysteresis(
            self,
            tiled_backend: TiledBackend,
            current_level: int,
            candidate_level: int,
            target_ds: float,
    ) -> int:
        """Decide whether to switch to an adjacent candidate level."""
        raise NotImplementedError


class BalancedLevelSelector(LevelSelector):
    """
    Balanced mode:
    - Selects the level closest to target_ds in log space.
    - Prefers coarser levels on ties to save memory/bandwidth.
    - Applies hysteresis around the geometric mean boundary of adjacent levels.
    """

    def best_level(self, tiled_backend: TiledBackend, target_ds: float) -> int:
        if tiled_backend.level_count == 0:
            return 0
        if not math.isfinite(target_ds) or target_ds <= 0.0:
            return tiled_backend.level_count - 1

        log_target = math.log(max(target_ds, _MIN_EPS))
        best_level = 0
        best_diff = math.inf
        best_ds = max(tiled_backend.level_downsample(best_level), _MIN_EPS)

        for level in range(tiled_backend.level_count):
            ds = max(tiled_backend.level_downsample(level), _MIN_EPS)
            diff = abs(math.log(ds) - log_target)

            if diff < best_diff - _MIN_EPS:
                best_level = level
                best_diff = diff
                best_ds = ds
            elif abs(diff - best_diff) <= _MIN_EPS and ds > best_ds:
                # Tie-breaker: prefer coarser level (higher downsample)
                best_level = level
                best_diff = diff
                best_ds = ds

        return best_level

    def _resolve_adjacent_hysteresis(
        self,
        tiled_backend: TiledBackend,
        current_level: int,
        candidate_level: int,
        target_ds: float,
    ) -> int:
        ds_current = max(tiled_backend.level_downsample(current_level), _MIN_EPS)
        ds_candidate = max(tiled_backend.level_downsample(candidate_level), _MIN_EPS)

        # Geometric mean boundary between adjacent levels
        boundary = math.sqrt(ds_current * ds_candidate)
        margin = self.hysteresis_margin

        if candidate_level > current_level:
            # Zooming out (candidate is coarser)
            if target_ds > boundary * (1.0 + margin):
                return candidate_level
        else:
            # Zooming in (candidate is finer)
            if target_ds < boundary / (1.0 + margin):
                return candidate_level

        return current_level


class SharpLevelSelector(LevelSelector):
    """
    Sharp mode:
    - Prioritizes detail: level_downsample <= target_downsample.
    - Switches to finer levels immediately on zoom in.
    - Delays switching to coarser levels on zoom out (hysteresis).
    """

    def best_level(self, tiled_backend: TiledBackend, target_ds: float) -> int:
        if tiled_backend.level_count == 0:
            return 0
        if not math.isfinite(target_ds) or target_ds <= 0.0:
            return tiled_backend.level_count - 1

        # Find the coarsest level that is still sharper than or equal to target_ds
        candidate = 0
        for level in range(tiled_backend.level_count):
            ds = tiled_backend.level_downsample(level)
            if ds <= target_ds * (1.0 + _MIN_EPS):
                candidate = level
            else:
                break
        return candidate

    def _resolve_adjacent_hysteresis(
        self,
        tiled_backend: TiledBackend,
        current_level: int,
        candidate_level: int,
        target_ds: float,
    ) -> int:
        if candidate_level < current_level:
            # Zooming in: always switch to finer level to maintain sharpness
            return candidate_level

        # Zooming out: candidate is coarser.
        # Only switch if target_ds significantly exceeds the candidate's downsample.
        ds_candidate = tiled_backend.level_downsample(candidate_level)
        if target_ds > ds_candidate * (1.0 + self.hysteresis_margin):
            return candidate_level

        return current_level
