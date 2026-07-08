"""Task type registry for SE8 worker.

Allows registering task type detectors without modifying _detect_task_type().
Each detector is a callable that takes a request dict and returns TaskType or None.
"""
from __future__ import annotations

from typing import Any, Callable

from app.domain.task_models import TaskType


class TaskTypeRegistry:
    """Registry for task type detection."""

    def __init__(self) -> None:
        self._detectors: list[Callable[[dict[str, Any]], TaskType | None]] = []

    def register(self, detector: Callable[[dict[str, Any]], TaskType | None]) -> None:
        """Register a task type detector function."""
        self._detectors.append(detector)

    def detect(self, req: dict[str, Any]) -> TaskType:
        """Detect task type from request using registered detectors.

        Returns first matching TaskType, or TEXT_TO_IMAGE as default.
        """
        for detector in self._detectors:
            result = detector(req)
            if result is not None:
                return result
        return TaskType.TEXT_TO_IMAGE


def create_default_registry() -> TaskTypeRegistry:
    """Create a registry with the built-in task type detectors."""
    registry = TaskTypeRegistry()

    def _detect_upscale(req: dict[str, Any]) -> TaskType | None:
        if req.get("current_tab") == "uov" or req.get("uov_input_image"):
            return TaskType.IMG_UPSCALE_VARY
        return None

    def _detect_inpaint(req: dict[str, Any]) -> TaskType | None:
        if req.get("current_tab") == "inpaint" or req.get("inpaint_input_image"):
            return TaskType.IMG_INPAINT_OUTPAINT
        return None

    def _detect_prompt(req: dict[str, Any]) -> TaskType | None:
        if req.get("current_tab") == "ip" or req.get("image_prompts"):
            return TaskType.IMG_PROMPT
        return None

    def _detect_enhance(req: dict[str, Any]) -> TaskType | None:
        if req.get("current_tab") == "enhance" or req.get("enhance_checkbox"):
            return TaskType.IMG_ENHANCE
        return None

    registry.register(_detect_upscale)
    registry.register(_detect_inpaint)
    registry.register(_detect_prompt)
    registry.register(_detect_enhance)

    return registry
