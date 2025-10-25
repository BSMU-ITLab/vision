from __future__ import annotations

from typing import Final, TYPE_CHECKING

from bsmu.vision.core.input.acceleration import StepAccelerator, StepAcceleratorConfig

if TYPE_CHECKING:
    from PySide6.QtGui import QWheelEvent


class RadiusScaler:
    """
    Performs accelerated exponential scaling of a radius, limited by min/max bounds.

    See `_ViewSmoothZoom` class for a detailed explanation (acceleration, invertibility and composability).
    """
    def __init__(
            self,
            min_radius: float,
            max_radius: float,
            scroll_sensitivity: float = 1,
            accelerator_config: StepAcceleratorConfig | None = None,
            scale_base: float = 1.1,
    ):
        self._min_radius: Final[float] = min_radius
        self._max_radius: Final[float] = max_radius
        self._scroll_sensitivity: Final[float] = scroll_sensitivity

        if accelerator_config is None:
            accelerator_config = StepAcceleratorConfig()
        self._accelerator = StepAccelerator(accelerator_config)

        self._scale_base = scale_base

    def scale_from_angle(self, current_radius: float, angle_delta_in_degrees: float) -> float:
        accelerated_delta = self._accelerator.accelerate(angle_delta_in_degrees)
        exponent = 0.02 * accelerated_delta * self._scroll_sensitivity
        factor = self._scale_base ** exponent
        return min(max(self._min_radius, current_radius * factor), self._max_radius)

    def scale(self, current_radius: float, wheel_event: QWheelEvent) -> float:
        angle_delta_in_degrees = wheel_event.angleDelta().y() / 8
        return self.scale_from_angle(current_radius, angle_delta_in_degrees)
