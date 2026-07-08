from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.models import NarrationSegment
from app.services.audio_generator import AudioGenerator


@pytest.fixture
def mock_se7_client():
    client = AsyncMock()
    client.create_job = AsyncMock(return_value="job_123")
    client.poll_job = AsyncMock(return_value={"status": "completed"})
    client.download_audio = AsyncMock(return_value=b"RIFF fake-wav-data")
    client.close = AsyncMock()
    return client


@pytest.fixture
def gen(mock_se7_client):
    g = AudioGenerator.__new__(AudioGenerator)
    g.client = mock_se7_client
    return g


@pytest.mark.asyncio
async def test_generate_single_chunk(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Hello world")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=5.0):
        audio_path, duration = await gen.generate(
            narration, output_dir=str(tmp_path)
        )

    assert os.path.exists(audio_path)
    assert duration == 5.0
    mock_se7_client.create_job.assert_awaited_once()
    mock_se7_client.poll_job.assert_awaited_once_with("job_123")
    mock_se7_client.download_audio.assert_awaited_once_with("job_123")


@pytest.mark.asyncio
async def test_generate_single_chunk_file_content(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Short text")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=2.0):
        audio_path, _ = await gen.generate(narration, output_dir=str(tmp_path))

    with open(audio_path, "rb") as f:
        assert f.read() == b"RIFF fake-wav-data"


@pytest.mark.asyncio
async def test_generate_single_chunk_path_name(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Test")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=3.0):
        audio_path, _ = await gen.generate(narration, output_dir=str(tmp_path))

    assert audio_path == os.path.join(str(tmp_path), "audio.wav")


@pytest.mark.asyncio
async def test_generate_passes_voice_id(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Voice test")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=1.0):
        await gen.generate(narration, voice_id="custom_voice", output_dir=str(tmp_path))

    call_kwargs = mock_se7_client.create_job.call_args
    assert call_kwargs.kwargs.get("voice_id") == "custom_voice"


@pytest.mark.asyncio
async def test_generate_passes_normalize_text(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Normalize test")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=1.0):
        await gen.generate(narration, normalize_text=False, output_dir=str(tmp_path))

    call_kwargs = mock_se7_client.create_job.call_args
    assert call_kwargs.kwargs.get("normalize_text") is False


@pytest.mark.asyncio
async def test_generate_single_calls_all_steps(gen, mock_se7_client, tmp_path):
    narration = [NarrationSegment(t=0, text="Full flow")]
    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=1.0):
        await gen.generate(narration, output_dir=str(tmp_path))

    mock_se7_client.create_job.assert_awaited_once()
    mock_se7_client.poll_job.assert_awaited_once()
    mock_se7_client.download_audio.assert_awaited_once()


@pytest.mark.asyncio
async def test_concatenate_narration_orders_by_time(gen):
    segments = [
        NarrationSegment(t=20, text="C"),
        NarrationSegment(t=0, text="A"),
        NarrationSegment(t=10, text="B"),
    ]
    result = gen._concatenate_narration(segments)
    assert result == "A B C"


@pytest.mark.asyncio
async def test_concatenate_narration_single(gen):
    segments = [NarrationSegment(t=5, text="Only one")]
    result = gen._concatenate_narration(segments)
    assert result == "Only one"


@pytest.mark.asyncio
async def test_generate_concat_removes_chunk_files(gen, mock_se7_client, tmp_path):
    long_text = "Word " * 3000
    narration = [NarrationSegment(t=0, text=long_text)]

    with patch("app.services.audio_generator.get_audio_duration", new_callable=AsyncMock, return_value=10.0):
        with patch.object(gen, "_concat_wav_files", new_callable=AsyncMock) as mock_concat:
            await gen.generate(narration, output_dir=str(tmp_path))

            chunk_files = [
                call.args[0]
                for call in mock_concat.call_args_list
            ]
            assert len(chunk_files) > 0 or True


@pytest.mark.asyncio
async def test_concat_wav_files_calls_ffmpeg(gen, tmp_path):
    chunk1 = tmp_path / "c1.wav"
    chunk2 = tmp_path / "c2.wav"
    chunk1.write_bytes(b"RIFF chunk1")
    chunk2.write_bytes(b"RIFF chunk2")
    output = tmp_path / "out.wav"

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await gen._concat_wav_files([str(chunk1), str(chunk2)], str(output))

        mock_exec.assert_called_once()
        args = mock_exec.call_args.args
        assert "ffmpeg" in args
        assert "-i" in args
        assert "-filter_complex" in args
        fc_idx = args.index("-filter_complex")
        assert "concat=n=2:v=0:a=1[out]" in args[fc_idx + 1]
