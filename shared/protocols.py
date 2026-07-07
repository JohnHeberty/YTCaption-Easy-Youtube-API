"""Protocols (interfaces) for dependency inversion across services.

These Protocol classes define the contracts that concrete implementations
must satisfy. High-level modules depend on these abstractions, not on
concrete implementations.

Usage:
    from shared.protocols import DetectorProtocol, InpaintClientProtocol

    def process(detector: DetectorProtocol) -> dict:
        result = detector.detect(image)
        ...
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ─── SE10 Detector Protocol ─────────────────────────────────────────────────

@runtime_checkable
class DetectorProtocol(Protocol):
    """Protocol for SE10 clothing/person detectors.

    Any detector (SegFormer, YOLO, Ensemble) must implement this interface.
    """

    def predict(
        self,
        image_bgr: Any,  # np.ndarray
        confidence: float = 0.25,
        classes: list[int] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run detection on BGR image. Returns supervision.Detections."""
        ...


@runtime_checkable
class SegmentorProtocol(Protocol):
    """Protocol for the SE10 segmentor (ClothesSegmentor)."""

    def segment(
        self,
        image_bytes: bytes,
        classes: list[str] | None = None,
        box_threshold: float | None = None,
        text_threshold: float | None = None,
        max_area_pct: float | None = None,
        max_objects: int | None = None,
        mode: str = "clothes",
        detector: str = "segformer",
        include_pose: bool = False,
    ) -> dict[str, Any]:
        """Run full segmentation pipeline. Returns result dict."""
        ...

    def unload_all(self) -> None:
        """Unload all models."""
        ...

    def unload_gpu_models(self) -> None:
        """Unload GPU models only."""
        ...


# ─── SE8 Client Protocols ───────────────────────────────────────────────────

@runtime_checkable
class InpaintClientProtocol(Protocol):
    """Protocol for SE8 inpainting operations."""

    async def inpaint(
        self,
        image_b64: str,
        mask_b64: str,
        prompt: str = "",
        negative_prompt: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run inpainting on image with mask. Returns result dict."""
        ...


@runtime_checkable
class UpscaleClientProtocol(Protocol):
    """Protocol for SE8 upscale operations."""

    async def upscale(
        self,
        image_b64: str,
        scale: float = 2.0,
    ) -> dict[str, Any]:
        """Upscale image. Returns result dict with base64."""
        ...


@runtime_checkable
class FaceRestoreClientProtocol(Protocol):
    """Protocol for SE8 face restoration operations."""

    async def restore_face(
        self,
        image_b64: str,
        model: str = "CodeFormer",
        fidelity: float = 0.5,
    ) -> dict[str, Any]:
        """Restore faces in image. Returns result dict."""
        ...


@runtime_checkable
class SE8ClientProtocol(InpaintClientProtocol, UpscaleClientProtocol, FaceRestoreClientProtocol, Protocol):
    """Combined protocol for all SE8 operations.

    A client that implements all three capabilities.
    """

    async def close(self) -> None:
        """Close the HTTP client."""
        ...

    async def health(self) -> dict[str, Any]:
        """Check SE8 health."""
        ...


# ─── SE10 Client Protocol ───────────────────────────────────────────────────

@runtime_checkable
class SE10ClientProtocol(Protocol):
    """Protocol for SE10 HTTP client."""

    async def segment(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
        classes: str | None = None,
        box_threshold: float | None = None,
        text_threshold: float | None = None,
        mode: str = "clothes",
        detector: str = "groundingdino",
        include_pose: bool = False,
    ) -> dict[str, Any]:
        """Send image to SE10 for segmentation."""
        ...

    async def close(self) -> None:
        """Close the HTTP client."""
        ...

    async def health(self) -> dict[str, Any]:
        """Check SE10 health."""
        ...


# ─── Job Store Protocol ─────────────────────────────────────────────────────

@runtime_checkable
class JobStoreProtocol(Protocol):
    """Protocol for job persistence (Redis, in-memory, etc.)."""

    def save_job(self, job_id: str, data: dict[str, Any]) -> None:
        """Save job data."""
        ...

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job data by ID. Returns None if not found."""
        ...

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all jobs."""
        ...

    def delete_job(self, job_id: str) -> None:
        """Delete job."""
        ...


# ─── Pose Detector Protocol ─────────────────────────────────────────────────

@runtime_checkable
class PoseDetectorProtocol(Protocol):
    """Protocol for pose detection (DWPose, MediaPipe, etc.)."""

    def detect(
        self,
        image: Any,  # np.ndarray
        min_detection_confidence: float = 0.5,
    ) -> Any | None:
        """Detect pose in image. Returns PoseResult or None."""
        ...


# ─── Face Detector Protocol ─────────────────────────────────────────────────

@runtime_checkable
class FaceDetectorProtocol(Protocol):
    """Protocol for face detection (MediaPipe, haarcascade, etc.)."""

    def detect_faces(
        self,
        image: Any,  # np.ndarray
    ) -> list[tuple[int, int, int, int]]:
        """Detect faces in image. Returns list of (x, y, w, h) bboxes."""
        ...


# ─── Service Client Protocol ────────────────────────────────────────────────

@runtime_checkable
class ServiceClientProtocol(Protocol):
    """Base protocol for HTTP service clients."""

    async def close(self) -> None:
        """Close the HTTP client."""
        ...

    async def health(self) -> dict[str, Any]:
        """Check service health."""
        ...
