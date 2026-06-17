import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def task_queue():
    from app.services.task_queue import TaskQueue
    return TaskQueue(queue_size=100, history_size=64)


@pytest.fixture
def sample_task_params():
    return {
        "prompt": "a beautiful sunset",
        "negative_prompt": "",
        "style_selections": ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"],
        "performance_selection": "Speed",
        "aspect_ratios_selection": "1024×1024",
        "image_number": 1,
        "image_seed": 42,
        "sharpness": 2.0,
        "guidance_scale": 4.0,
        "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
        "refiner_model_name": "None",
        "refiner_switch": 0.5,
        "loras": [(True, "None", 0.5)],
        "uov_method": "Disabled",
        "output_format": "png",
        "require_base64": False,
        "async_process": False,
    }
