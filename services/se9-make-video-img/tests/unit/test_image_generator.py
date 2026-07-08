from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import IMAGE_ASPECT_RATIOS
from app.core.models import SceneSuggestion
from app.services.image_generator import ImageGenerator


@pytest.fixture
def mock_se8_client():
    client = AsyncMock()
    client.generate_image = AsyncMock(
        return_value=[{"url": "/files/2026-07-08/scene.png"}]
    )
    client.download_image = AsyncMock(return_value=b"\x89PNG\r\nfake")
    client.close = AsyncMock()
    return client


@pytest.fixture
def gen(mock_se8_client):
    return ImageGenerator(client=mock_se8_client)


def test_init_sets_cinematic_suffix():
    gen = ImageGenerator()
    assert "cinematic composition" in gen.cinematic_suffix
    assert "8k resolution" in gen.cinematic_suffix


def test_init_custom_cinematic_suffix():
    gen = ImageGenerator(cinematic_suffix=", custom suffix")
    assert gen.cinematic_suffix == ", custom suffix"


def test_init_default_client_created():
    with patch("app.services.image_generator.SE8Client") as MockSE8:
        gen = ImageGenerator()
        MockSE8.assert_called_once()


def test_get_dimensions_known_ratio(gen):
    assert gen._get_dimensions("9:16") == (1024, 1792)
    assert gen._get_dimensions("16:9") == (1792, 1024)
    assert gen._get_dimensions("1:1") == (1024, 1024)


def test_get_dimensions_unknown_ratio(gen):
    assert gen._get_dimensions("4:3") == (1024, 1792)


@pytest.mark.asyncio
async def test_generate_all_empty_scenes(gen):
    result = await gen.generate_all([], output_dir="/tmp")
    assert result == []
    gen.client.generate_image.assert_not_called()


@pytest.mark.asyncio
async def test_generate_all_calls_se8_for_each_scene(gen, mock_se8_client, tmp_path):
    scenes = [
        SceneSuggestion(t=0, visual="A cat on Mars"),
        SceneSuggestion(t=10, visual="A dog on Moon"),
    ]
    result = await gen.generate_all(scenes, output_dir=str(tmp_path))

    assert mock_se8_client.generate_image.call_count == 2
    assert mock_se8_client.download_image.call_count == 2
    assert len(result) == 2
    for path in result:
        assert os.path.exists(path)


@pytest.mark.asyncio
async def test_generate_all_saves_files_with_correct_names(gen, mock_se8_client, tmp_path):
    scenes = [SceneSuggestion(t=5, visual="Sunset")]
    result = await gen.generate_all(scenes, output_dir=str(tmp_path))

    assert len(result) == 1
    assert result[0] == os.path.join(str(tmp_path), "scene_5.png")
    with open(result[0], "rb") as f:
        assert f.read() == b"\x89PNG\r\nfake"


@pytest.mark.asyncio
async def test_generate_all_appends_cinematic_suffix(gen, mock_se8_client, tmp_path):
    scenes = [SceneSuggestion(t=0, visual="Mountain view")]
    await gen.generate_all(scenes, output_dir=str(tmp_path))

    call_kwargs = mock_se8_client.generate_image.call_args
    prompt = call_kwargs.kwargs.get("prompt") or call_kwargs[1].get("prompt")
    assert "Mountain view" in prompt
    assert "cinematic composition" in prompt


@pytest.mark.asyncio
async def test_generate_all_passes_negative_prompt(gen, mock_se8_client, tmp_path):
    scenes = [SceneSuggestion(t=0, visual="Beach", negative_prompt="blurry, low quality")]
    await gen.generate_all(scenes, output_dir=str(tmp_path))

    call_kwargs = mock_se8_client.generate_image.call_args
    neg = call_kwargs.kwargs.get("negative_prompt") or call_kwargs[1].get("negative_prompt")
    assert neg == "blurry, low quality"


@pytest.mark.asyncio
async def test_generate_all_sorted_by_time(gen, mock_se8_client, tmp_path):
    scenes = [
        SceneSuggestion(t=20, visual="Second"),
        SceneSuggestion(t=5, visual="First"),
    ]
    await gen.generate_all(scenes, output_dir=str(tmp_path))

    calls = mock_se8_client.generate_image.call_args_list
    first_prompt = calls[0].kwargs.get("prompt") or calls[0][1].get("prompt")
    second_prompt = calls[1].kwargs.get("prompt") or calls[1][1].get("prompt")
    assert "First" in first_prompt
    assert "Second" in second_prompt


@pytest.mark.asyncio
async def test_generate_all_calls_progress_callback(gen, mock_se8_client, tmp_path):
    scenes = [
        SceneSuggestion(t=0, visual="A"),
        SceneSuggestion(t=10, visual="B"),
    ]
    cb = AsyncMock()
    await gen.generate_all(scenes, output_dir=str(tmp_path), progress_callback=cb)

    assert cb.call_count == 2
    first_call = cb.call_args_list[0][0][0]
    second_call = cb.call_args_list[1][0][0]
    assert first_call == pytest.approx(50.0)
    assert second_call == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_generate_all_raises_on_no_url(gen, mock_se8_client, tmp_path):
    mock_se8_client.generate_image.return_value = [{"no_url": True}]
    scenes = [SceneSuggestion(t=0, visual="X")]

    with pytest.raises(ValueError, match="No URL in SE8 response"):
        await gen.generate_all(scenes, output_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_generate_all_passes_correct_dimensions(gen, mock_se8_client, tmp_path):
    scenes = [SceneSuggestion(t=0, visual="Wide shot")]
    await gen.generate_all(scenes, aspect_ratio="16:9", output_dir=str(tmp_path))

    call_kwargs = mock_se8_client.generate_image.call_args
    assert call_kwargs.kwargs.get("width") == 1792
    assert call_kwargs.kwargs.get("height") == 1024


@pytest.mark.asyncio
async def test_close(gen):
    await gen.close()
    gen.client.close.assert_awaited_once()
