import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class StepAcceleratorConfig:
    reset_timeout_ms: float = 300.0  # Time window (ms) after which acceleration resets if no further input occurs
    increment_max: float = 4.0       # Maximum increment added to the multiplier when inputs are very close together
    multiplier_max: float = 10.0     # Upper bound for the acceleration multiplier


class StepAccelerator:
    """
    Utility for applying time-sensitive acceleration to repeated step inputs.

    Consecutive steps in the same direction within a short time window
    increase the effective step size by raising a multiplier.
    Pauses or direction changes reset the multiplier back to 1.0.
    """

    def __init__(self, config: StepAcceleratorConfig | None = None):
        if config is None:
            config = StepAcceleratorConfig()
        self._config = config

        self._last_timestamp_ms: float = 0.0
        self._last_direction: int = 0  # +1 for forward, -1 for backward
        self._multiplier: float = 1.0

    def accelerate(self, step: float) -> float:
        direction = int(math.copysign(1, step))
        current_timestamp_ms = time.monotonic() * 1000
        elapsed_ms = current_timestamp_ms - self._last_timestamp_ms

        if direction != self._last_direction or elapsed_ms > self._config.reset_timeout_ms:
            # Reset multiplier
            self._multiplier = 1.0
        else:
            # Increase the multiplier proportionally to input frequency:
            # the shorter the time since the previous call, the larger the increment.
            multiplier_increment = self._config.increment_max * (1 - elapsed_ms / self._config.reset_timeout_ms)
            self._multiplier = min(self._multiplier + multiplier_increment, self._config.multiplier_max)

        self._last_direction = direction
        self._last_timestamp_ms = current_timestamp_ms
        return step * self._multiplier
