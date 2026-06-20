"""Shared test fixtures for SE11 Clothes Removal tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    """Mock Redis store."""
    store = MagicMock()
    store.save_job = MagicMock()
    store.get_job = MagicMock(return_value=None)
    store.list_jobs = MagicMock(return_value=[])
    store.delete_job = MagicMock()
    return store


@pytest.fixture
def mock_se10_response():
    """Mock SE10 segmentation response."""
    return {
        "detected": True,
        "object_count": 2,
        "objects": [
            {
                "class_name": "shirt",
                "confidence": 0.87,
                "bbox": [120, 45, 380, 300],
                "area_pct": 12.5,
            },
            {
                "class_name": "pants",
                "confidence": 0.75,
                "bbox": [100, 300, 400, 600],
                "area_pct": 20.0,
            },
        ],
        "masks": [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg==",
        ],
        "mask_image": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
        "processing_time_ms": 1234.5,
    }


@pytest.fixture
def mock_se8_response():
    """Mock SE8 inpainting response."""
    return {
        "base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "url": "/files/2026-06-19/result.png",
        "seed": 12345,
        "finish_reason": "SUCCESS",
    }


@pytest.fixture
def sample_create_request():
    """Sample create job request payload."""
    return {
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
        "classes": "shirt,pants",
        "prompt": "nude, naked body",
        "negative_prompt": "clothes, fabric",
        "box_threshold": 0.10,
        "text_threshold": 0.10,
        "inpaint_strength": 1.0,
    }
