"""Audio conversion and validation using ffmpeg/ffprobe."""
from __future__ import annotations

import json
import subprocess as sp  # noqa: F401 – re-exported for convert_to_wav internals

from common.log_utils import get_logger

logger = get_logger(__name__)
from pathlib import Path

subprocess = sp  # alias used inside try/except blocks


def has_audio_stream(input_path: Path) -> tuple[bool, str]:
    """Check if a file contains an audio stream using ffprobe.

    Returns:
        (has_audio, info_string): True when at least one audio stream exists.
    """
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-select_streams', 'a', str(input_path)
    ]

    try:
        result = sp.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return True, "ffprobe indisponível, assumindo que tem áudio"

        probe_data = json.loads(result.stdout) if result.stdout.strip() else {}
        streams = probe_data.get('streams', [])

        if not streams:
            video_cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-select_streams', 'v', str(input_path)
            ]
            video_result = sp.run(video_cmd, capture_output=True, text=True, timeout=30)
            has_video = False
            if video_result.returncode == 0 and video_result.stdout.strip():
                video_data = json.loads(video_result.stdout)
                has_video = bool(video_data.get('streams', []))

            detail = "vídeo" if has_video else "texto/dados"
            return False, f"Arquivo contém apenas stream de {detail}, sem stream de áudio"

        codec = streams[0].get('codec_name', 'unknown')
        channels = streams[0].get('channels', '?')
        sample_rate = streams[0].get('sample_rate', '?')
        return True, f"áudio: codec={codec}, canais={channels}, taxa={sample_rate}"

    except json.JSONDecodeError:
        return True, "ffprobe retornou JSON inválido, assumindo que tem áudio"
    except FileNotFoundError:
        return True, "ffprobe não disponível, assumindo que tem áudio"
    except sp.TimeoutExpired:
        return True, "ffprobe timeout, assumindo que tem áudio"
    except Exception as e:
        return True, f"erro na verificação: {e}, assumindo que tem áudio"


def convert_to_wav(
    input_path: Path,
    settings: dict[str, object] | None = None,
) -> tuple[Path, bool]:
    """Convert any audio/video file to WAV 16kHz mono pcm_s16le.

    Supports MP4, OGG, MP3, M4A, WEBM, FLAC and more via ffmpeg.
    Files without an audio stream raise AudioTranscriptionException.

    Args:
        input_path: Source file path.
        settings: Optional config dict with keys ``temp_dir``,
            ``ffmpeg_sample_rate`` (default 16000), ``ffmpeg_threads`` (default 0).

    Returns:
        ``(wav_path, is_temp)`` — WAV file path and whether it's a temporary file.

    Raises:
        AudioTranscriptionException: If the file lacks audio or conversion fails.
    """
    from ..shared.exceptions import AudioTranscriptionException
    try:
        from pydub import AudioSegment as _AudioSegment  # noqa: F811
    except ImportError:
        raise AudioTranscriptionException("pydub não está instalado")

    if not input_path.exists():
        raise AudioTranscriptionException(
            f"Arquivo de entrada não encontrado: '{input_path}'"
        )

    if settings is None:
        settings = {}

    AUDIO_EXTENSIONS = {'.wav'}
    AUDIO_EXTENSIONS_NEEDING_CONVERT = {
        '.mp3', '.ogg', '.m4a', '.mp4', '.webm', '.flac', '.aac',
        '.wma', '.opus', '.3gp', '.ts', '.mxf', '.avi', '.mkv', '.mov'
    }

    ext = input_path.suffix.lower()

    if ext in AUDIO_EXTENSIONS:
        try:
            audio = _AudioSegment.from_file(str(input_path))
            if audio.frame_rate == 16000 and audio.channels == 1:
                return input_path, False
        except Exception as e:
            logger.debug("Probe of %s failed: %s", input_path, e)
        return input_path, False

    if ext not in AUDIO_EXTENSIONS_NEEDING_CONVERT and ext not in AUDIO_EXTENSIONS:
        pass  # attempt conversion anyway

    has_audio, audio_info = has_audio_stream(input_path)
    if not has_audio:
        raise AudioTranscriptionException(
            f"Não é possível transcrever o arquivo '{input_path.name}': "
            f"{audio_info}. "
            f"O arquivo precisa conter pelo menos um stream de áudio para ser transcrito. "
            f"Verifique se o arquivo de vídeo foi gravado com áudio."
        )

    temp_dir = Path(settings.get('temp_dir', './data/temp'))
    temp_dir.mkdir(parents=True, exist_ok=True)

    wav_filename = f"{input_path.stem}_converted.wav"
    wav_path = temp_dir / wav_filename

    sample_rate = str(settings.get('ffmpeg_sample_rate', '16000'))
    threads = str(settings.get('ffmpeg_threads', '0'))

    cmd = [
        'ffmpeg', '-i', str(input_path), '-vn',
        '-acodec', 'pcm_s16le', '-ar', sample_rate, '-ac', '1',
        '-threads', threads, '-y', str(wav_path)
    ]

    try:
        result = sp.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            stderr_preview = result.stderr[:500] if result.stderr else "no stderr"
            raise AudioTranscriptionException(
                f"Falha ao converter áudio para WAV (ffmpeg exit code {result.returncode}): {stderr_preview}"
            )

        if not wav_path.exists() or wav_path.stat().st_size < 100:
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)
            raise AudioTranscriptionException(
                f"O arquivo '{input_path.name}' não pôde ser convertido para WAV. "
                f"Isso geralmente ocorre quando o arquivo não contém stream de áudio válido "
                f"(ex: vídeo sem áudio, arquivo corrompido, ou formato não suportado). "
                f"Verifique se o arquivo contém áudio antes de enviar para transcrição."
            )

        return wav_path, True

    except sp.TimeoutExpired:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)
        raise AudioTranscriptionException(
            f"Timeout ao converter áudio para WAV (limite: 300s): {input_path.name}"
        )
    except AudioTranscriptionException:
        raise
    except Exception as e:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)
        raise AudioTranscriptionException(f"Erro ao converter áudio para WAV: {str(e)}")
