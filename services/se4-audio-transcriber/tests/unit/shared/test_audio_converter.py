"""Unit tests for AudioConverter (has_audio_stream, convert_to_wav)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.shared.audio_converter import has_audio_stream, convert_to_wav


# ---------------------------------------------------------------------------
# Fixtures – minimal valid media files on disk
# ---------------------------------------------------------------------------


@pytest.fixture()
def mp3_file(tmp_path: Path) -> Path:
    """Create a dummy .mp3 file (non-empty bytes)."""
    p = tmp_path / "sample.mp3"
    # Write enough bytes so ffmpeg size check (>100) passes.
    p.write_bytes(b"\x00" * 200)
    return p


@pytest.fixture()
def wav_file(tmp_path: Path) -> Path:
    """Create a dummy .wav file."""
    p = tmp_path / "sample.wav"
    p.write_bytes(b"\x00" * 200)
    return p


# ---------------------------------------------------------------------------
# has_audio_stream – ffprobe JSON probing
# ---------------------------------------------------------------------------


class TestHasAudioStream:

    def test_detects_audio_stream(self, mp3_file):
        """ffprobe returns at least one audio stream -> True."""
        probe_json = json.dumps({
            "streams": [
                {"codec_name": "mp3", "channels": 2, "sample_rate": "44100"}
            ]
        })

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = probe_json

        with patch("app.shared.audio_converter.sp.run", return_value=mock_result):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is True
        assert "codec=mp3" in info
        assert "canais=2" in info
        assert "taxa=44100" in info

    def test_no_audio_only_video(self, mp3_file):
        """No audio streams but video present -> False with 'vídeo' detail."""
        # First call: no audio streams.
        mock_run = MagicMock(side_effect=[
            MagicMock(returncode=0, stdout=json.dumps({"streams": []})),
            # Second call (video probe): has video stream.
            MagicMock(
                returncode=0,
                stdout=json.dumps({"streams": [{"codec_name": "h264"}]}),
            ),
        ])

        with patch("app.shared.audio_converter.sp.run", mock_run):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is False
        assert "vídeo" in info.lower()

    def test_no_audio_no_video(self, mp3_file):
        """No audio and no video streams -> False with 'texto/dados' detail."""
        mock_run = MagicMock(side_effect=[
            MagicMock(returncode=0, stdout=json.dumps({"streams": []})),
            # Video probe: empty.
            MagicMock(returncode=0, stdout=""),
        ])

        with patch("app.shared.audio_converter.sp.run", mock_run):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is False
        assert "texto/dados" in info.lower()

    def test_ffprobe_not_found_fallback(self, mp3_file):
        """FileNotFoundError from ffprobe -> True (safe fallback)."""
        with patch("app.shared.audio_converter.sp.run", side_effect=FileNotFoundError()):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is True
        assert "não disponível" in info.lower()

    def test_ffprobe_invalid_json_fallback(self, mp3_file):
        """Non-JSON stdout -> JSONDecodeError -> True (safe fallback)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not-json-at-all"

        with patch("app.shared.audio_converter.sp.run", return_value=mock_result):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is True
        assert "json inválido" in info.lower()

    def test_ffprobe_timeout_fallback(self, mp3_file):
        """TimeoutExpired -> True (safe fallback)."""
        import subprocess as sp

        with patch("app.shared.audio_converter.sp.run", side_effect=sp.TimeoutExpired(cmd="ffprobe", timeout=30)):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is True
        assert "timeout" in info.lower()

    def test_ffprobe_nonzero_returncode_fallback(self, mp3_file):
        """returncode != 0 -> True (safe fallback)."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("app.shared.audio_converter.sp.run", return_value=mock_result):
            has_audio, info = has_audio_stream(mp3_file)

        assert has_audio is True


# ---------------------------------------------------------------------------
# convert_to_wav – ffmpeg conversion pipeline
# ---------------------------------------------------------------------------


class TestConvertToWav:

    def test_converts_mp3_to_wav(self, mp3_file):
        """MP3 file goes through ffmpeg and produces a WAV on disk."""
        # has_audio_stream returns True.
        mock_probe = MagicMock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": "mp3", "channels": 2, "sample_rate": "44100"}]
        }))

        def fake_run(cmd, **kwargs):
            # When ffmpeg is called (cmd[0]=='ffmpeg'), create the output WAV.
            if cmd[0] == "ffmpeg" and "-acodec" in cmd:
                out_path = Path(str(cmd[-1]))  # last arg is -y <output>
                out_path.write_bytes(b"\x00" * 500)
                return MagicMock(returncode=0, stderr="", stdout="")
            return mock_probe

        with patch("app.shared.audio_converter.sp.run", side_effect=fake_run):
            wav_path, is_temp = convert_to_wav(mp3_file)

        assert wav_path.exists()
        assert wav_path.suffix == ".wav"
        assert is_temp is True

    def test_converts_with_custom_settings(self, mp3_file, tmp_path):
        """Custom temp_dir and sample_rate are respected."""
        custom_tmp = tmp_path / "custom_wavs"
        settings = {
            "temp_dir": str(custom_tmp),
            "ffmpeg_sample_rate": 48000,
            "ffmpeg_threads": 4,
        }

        mock_probe = MagicMock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": "mp3", "channels": 1, "sample_rate": "48000"}]
        }))

        captured_cmd = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg" and "-acodec" in cmd:
                captured_cmd.append(list(cmd))
                out_path = Path(str(cmd[-1]))
                out_path.write_bytes(b"\x00" * 500)
                return MagicMock(returncode=0, stderr="", stdout="")
            return mock_probe

        with patch("app.shared.audio_converter.sp.run", side_effect=fake_run):
            wav_path, _ = convert_to_wav(mp3_file, settings=settings)

        assert custom_tmp in wav_path.parents or str(custom_tmp) == str(wav_path.parent)
        # Verify ffmpeg was called with the right sample rate and threads.
        cmd = captured_cmd[0]
        assert "-ar" in cmd
        ar_idx = cmd.index("-ar")
        assert cmd[ar_idx + 1] == "48000"
        assert "-threads" in cmd
        t_idx = cmd.index("-threads")
        assert cmd[t_idx + 1] == "4"

    def test_raises_when_no_audio_stream(self, mp3_file):
        """File without audio raises AudioTranscriptionException."""
        mock_probe = MagicMock(returncode=0, stdout=json.dumps({"streams": []}))

        with patch("app.shared.audio_converter.sp.run", return_value=mock_probe):
            from app.shared.exceptions import AudioTranscriptionException

            with pytest.raises(AudioTranscriptionException, match="stream de áudio"):
                convert_to_wav(mp3_file)

    def test_raises_on_ffmpeg_failure(self, mp3_file):
        """ffmpeg returning non-zero exit code raises exception."""
        mock_probe = MagicMock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": "mp3"}]
        }))

        ffmpeg_fail = MagicMock(
            returncode=1, stderr="Conversion failed", stdout=""
        )

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg" and "-acodec" in cmd:
                return ffmpeg_fail
            return mock_probe

        with patch("app.shared.audio_converter.sp.run", side_effect=fake_run):
            from app.shared.exceptions import AudioTranscriptionException

            with pytest.raises(AudioTranscriptionException, match="exit code 1"):
                convert_to_wav(mp3_file)

    def test_raises_on_conversion_timeout(self, mp3_file):
        """ffmpeg timing out raises exception and cleans up partial file."""
        import subprocess as sp

        mock_probe = MagicMock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": "mp3"}]
        }))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg" and "-acodec" in cmd:
                out_path = Path(str(cmd[-1]))
                out_path.write_bytes(b"\x00" * 50)  # partial file
                raise sp.TimeoutExpired(cmd="ffmpeg", timeout=300)
            return mock_probe

        with patch("app.shared.audio_converter.sp.run", side_effect=fake_run):
            from app.shared.exceptions import AudioTranscriptionException

            with pytest.raises(AudioTranscriptionException, match="[Tt]imeout"):
                convert_to_wav(mp3_file)

    def test_raises_on_small_output(self, mp3_file):
        """Output file < 100 bytes is treated as conversion failure."""
        mock_probe = MagicMock(returncode=0, stdout=json.dumps({
            "streams": [{"codec_name": "mp3"}]
        }))

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg" and "-acodec" in cmd:
                out_path = Path(str(cmd[-1]))
                out_path.write_bytes(b"\x00" * 50)  # too small (< 100 bytes)
                return MagicMock(returncode=0, stderr="", stdout="")
            return mock_probe

        with patch("app.shared.audio_converter.sp.run", side_effect=fake_run):
            from app.shared.exceptions import AudioTranscriptionException

            with pytest.raises(AudioTranscriptionException, match="não pôde ser convertido"):
                convert_to_wav(mp3_file)


# ---------------------------------------------------------------------------
# convert_to_wav – WAV passthrough (already .wav extension)
# ---------------------------------------------------------------------------


class TestConvertToWavPassthrough:

    def test_already_valid_16k_mono_returns_same_path(self, wav_file):
        """A 16kHz mono WAV is returned as-is with is_temp=False."""
        mock_segment = MagicMock()
        mock_segment.frame_rate = 16000
        mock_segment.channels = 1

        pydub_mock = MagicMock()
        pydub_mock.AudioSegment.from_file.return_value = mock_segment

        with patch.dict("sys.modules", {"pydub": pydub_mock}):
            wav_path, is_temp = convert_to_wav(wav_file)

        assert wav_path == wav_file
        assert is_temp is False

    def test_non_standard_sample_rate_returns_same_path(self, wav_file):
        """A WAV with non-16kHz sample rate still returns same path (no reconvert)."""
        mock_segment = MagicMock()
        mock_segment.frame_rate = 44100
        mock_segment.channels = 2

        pydub_mock = MagicMock()
        pydub_mock.AudioSegment.from_file.return_value = mock_segment

        with patch.dict("sys.modules", {"pydub": pydub_mock}):
            wav_path, is_temp = convert_to_wav(wav_file)

        assert wav_path == wav_file
        assert is_temp is False

    def test_corrupt_wav_returns_same_path(self, wav_file):
        """A WAV that fails to load still returns same path (no reconvert)."""
        pydub_mock = MagicMock()
        pydub_mock.AudioSegment.from_file.side_effect = Exception("corrupt")

        with patch.dict("sys.modules", {"pydub": pydub_mock}):
            wav_path, is_temp = convert_to_wav(wav_file)

        assert wav_path == wav_file
        assert is_temp is False


# ---------------------------------------------------------------------------
# convert_to_wav – missing pydub
# ---------------------------------------------------------------------------


class TestConvertToWavMissingPyDub:

    def test_raises_when_pydub_not_installed(self, mp3_file):
        """ImportError on pydub raises AudioTranscriptionException."""
        with patch.dict("sys.modules", {"pydub": None}):
            from app.shared.exceptions import AudioTranscriptionException

            with pytest.raises(AudioTranscriptionException, match="não está instalado"):
                convert_to_wav(mp3_file)
