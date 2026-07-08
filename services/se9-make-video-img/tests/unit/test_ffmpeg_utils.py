from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure import ffmpeg_utils


@pytest.mark.asyncio
async def test_get_audio_duration():
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"12.345\n", b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await ffmpeg_utils.get_audio_duration("/tmp/audio.wav")

    assert result == pytest.approx(12.345)


@pytest.mark.asyncio
async def test_get_audio_duration_failure():
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="ffprobe failed"):
            await ffmpeg_utils.get_audio_duration("/tmp/bad.wav")


@pytest.mark.asyncio
async def test_create_segment_zoom_in():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.create_segment(
            image_path="/tmp/img.png",
            output_path="/tmp/seg.mp4",
            duration=5.0,
            width=1080,
            height=1920,
            fps=30,
            zoom_style="zoom_in",
        )

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert "ffmpeg" in args
    assert "-loop" in args
    assert "-i" in args
    assert "libx264" in args
    vf = args[args.index("-vf") + 1]
    assert "zoompan" in vf
    assert "zoom_in" not in vf or "zoom" in vf
    assert "1.0+" in vf


@pytest.mark.asyncio
async def test_create_segment_zoom_out():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.create_segment(
            image_path="/tmp/img.png",
            output_path="/tmp/seg.mp4",
            duration=5.0,
            width=1080,
            height=1920,
            fps=30,
            zoom_style="zoom_out",
        )

    args = mock_run.call_args.args[0]
    vf = args[args.index("-vf") + 1]
    assert "1.2-" in vf


@pytest.mark.asyncio
async def test_create_segment_zoom_expression_contains_duration():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.create_segment(
            image_path="/tmp/img.png",
            output_path="/tmp/seg.mp4",
            duration=5.0,
            width=1080,
            height=1920,
            fps=30,
            zoom_style="zoom_in",
        )

    args = mock_run.call_args.args[0]
    vf = args[args.index("-vf") + 1]
    assert "on/150" in vf


@pytest.mark.asyncio
async def test_create_segment_codec_flags():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.create_segment(
            image_path="/tmp/img.png",
            output_path="/tmp/seg.mp4",
            duration=5.0,
            width=1080,
            height=1920,
            fps=30,
            zoom_style="zoom_in",
        )

    args = mock_run.call_args.args[0]
    assert "yuv420p" in args
    assert "main" in args
    assert "4.0" in args


@pytest.mark.asyncio
async def test_concat_segments_single_segment():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.concat_segments(
            segment_paths=["/tmp/seg.mp4"],
            output_path="/tmp/concat.mp4",
        )

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert "-i" in args
    assert "/tmp/seg.mp4" in args
    assert "/tmp/concat.mp4" in args
    assert "libx264" in args


@pytest.mark.asyncio
async def test_concat_simple_multiple_segments():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.concat_simple(
            segment_paths=["/tmp/a.mp4", "/tmp/b.mp4"],
            output_path="/tmp/out.mp4",
        )

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert "concat" in args
    assert "-safe" in args
    assert "0" in args
    assert "-c" in args
    assert "copy" in args

    list_path = "/tmp/out.mp4.txt"
    assert not os.path.exists(list_path)


@pytest.mark.asyncio
async def test_concat_simple_creates_list_file():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.concat_simple(
            segment_paths=["/tmp/a.mp4", "/tmp/b.mp4", "/tmp/c.mp4"],
            output_path="/tmp/out.mp4",
        )

    list_path = "/tmp/out.mp4.txt"
    assert not os.path.exists(list_path)


@pytest.mark.asyncio
async def test_add_audio():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.add_audio(
            video_path="/tmp/video.mp4",
            audio_path="/tmp/audio.wav",
            output_path="/tmp/final.mp4",
        )

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert "-i" in args
    idx_video = args.index("/tmp/video.mp4")
    idx_audio = args.index("/tmp/audio.wav")
    assert idx_video < idx_audio
    assert "aac" in args
    assert "44100" in args
    assert "2" in args
    assert "+faststart" in args


@pytest.mark.asyncio
async def test_trim_to_duration():
    mock_run = AsyncMock()

    with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
        await ffmpeg_utils.trim_to_duration(
            video_path="/tmp/video.mp4",
            duration=30.5,
            output_path="/tmp/trimmed.mp4",
        )

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert "-t" in args
    t_idx = args.index("-t")
    assert args[t_idx + 1] == "30.500"
    assert "libx264" in args
    assert "aac" in args


@pytest.mark.asyncio
async def test_concat_simple_single_segment_copies():
    mock_run = AsyncMock()
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(b"fake-segment")
        src = tmp.name
    dst = src + "_out.mp4"

    try:
        with patch.object(ffmpeg_utils, "run_ffmpeg", mock_run):
            await ffmpeg_utils.concat_simple(
                segment_paths=[src],
                output_path=dst,
            )

        mock_run.assert_not_called()
        assert os.path.exists(dst)
        with open(dst, "rb") as f:
            assert f.read() == b"fake-segment"
    finally:
        for p in (src, dst):
            if os.path.exists(p):
                os.remove(p)


@pytest.mark.asyncio
async def test_run_ffmpeg_raises_on_failure():
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="FFmpeg failed"):
            await ffmpeg_utils.run_ffmpeg(["ffmpeg", "-y"])
