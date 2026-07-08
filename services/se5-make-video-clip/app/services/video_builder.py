"""
Video Builder

Responsavel pela montagem de videos usando FFmpeg.
Implementa APENAS processamento de video - NAO baixa videos.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..shared.exceptions_v2 import (
    VideoCorruptedException,
    VideoEncodingException,
    VideoInvalidResolutionException,
    ConcatenationException,
    FFmpegFailedException,
    FFprobeFailedException,
)
from common.log_utils import get_logger
from .ffmpeg_helpers import (
    run_ffmpeg_cmd,
    run_ffprobe_cmd,
    get_audio_duration_ffprobe,
    validate_srt,
    get_subtitle_style,
)

logger = get_logger(__name__)

ASPECT_MAP = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}


def _build_crop_filter(position: str, width: int, height: int) -> str:
    """Build FFmpeg crop filter based on position."""
    if position == "top":
        return f"crop={width}:{height}:0:0"
    elif position == "bottom":
        return f"crop={width}:{height}:0:(ih-{height})"
    else:
        return f"crop={width}:{height}"


def _build_concat_filter(
    resolved_video_files: list[str],
    video_filter: str,
    remove_audio: bool,
) -> str:
    """Build FFmpeg filter_complex string for concatenation."""
    filter_parts: list[str] = []
    concat_video_inputs: list[str] = []

    for i in range(len(resolved_video_files)):
        filter_parts.append(f"[{i}:v]{video_filter}[v{i}]")
        concat_video_inputs.append(f"[v{i}]")

        if not remove_audio:
            filter_parts.append(
                f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}]"
            )

    if remove_audio:
        filter_parts.append(
            f"{''.join(concat_video_inputs)}concat=n={len(resolved_video_files)}:v=1:a=0[vout]"
        )
    else:
        interleaved: list[str] = []
        for i in range(len(resolved_video_files)):
            interleaved.append(f"[v{i}]")
            interleaved.append(f"[a{i}]")
        filter_parts.append(
            f"{''.join(interleaved)}"
            f"concat=n={len(resolved_video_files)}:v=1:a=1[vout][aout]"
        )

    return ";".join(filter_parts)


class VideoBuilder:
    """Construtor de videos usando FFmpeg"""

    def __init__(self, output_dir: str,
                 video_codec: str = "libx264",
                 audio_codec: str = "aac",
                 preset: str = "fast",
                 crf: int = 23) -> None:
        self.output_dir = Path(output_dir)
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.preset = preset
        self.crf = crf

        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"VideoBuilder initialized")
        logger.info(f"   Output dir: {self.output_dir}")
        logger.info(f"   Video codec: {self.video_codec}")
        logger.info(f"   Audio codec: {self.audio_codec}")
        logger.info(f"   Preset: {self.preset}")
        logger.info(f"   CRF: {self.crf}")

    async def convert_to_h264(self, input_path: str, output_path: str) -> str:
        """Converte video para H264 mantendo resolucao e proporcao originais."""
        logger.info(f"Converting to H264: {Path(input_path).name}")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", self.video_codec,
            "-profile:v", "main",
            "-level", "4.0",
            "-g", "30",
            "-bf", "2",
            "-preset", self.preset,
            "-crf", str(self.crf),
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-y",
            output_path,
        ]

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=600, operation="H264 conversion",
            details={"input": input_path, "output": output_path},
        )

        if returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise FFmpegFailedException(
                operation="H264 conversion",
                stderr=error_msg,
                returncode=returncode,
                details={"input": input_path, "output": output_path},
            )

        logger.info(f"H264 conversion complete: {output_path}")
        return output_path

    async def concatenate_videos(self,
                                 video_files: list[str],
                                 output_path: str,
                                 aspect_ratio: str = "9:16",
                                 crop_position: str = "center",
                                 remove_audio: bool = True) -> str:
        """Concatena multiplos videos aplicando crop para aspect ratio."""
        logger.info(f"Concatenating {len(video_files)} videos")
        logger.info(f"   Aspect ratio: {aspect_ratio}")
        logger.info(f"   Crop position: {crop_position}")
        logger.info(f"   Remove audio: {remove_audio}")

        video_files = await self._ensure_compatibility(video_files)

        if aspect_ratio not in ASPECT_MAP:
            raise VideoInvalidResolutionException(
                aspect_ratio=aspect_ratio,
                valid_ratios=list(ASPECT_MAP.keys()),
            )

        target_width, target_height = ASPECT_MAP[aspect_ratio]

        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase"
        crop_filter = _build_crop_filter(crop_position, target_width, target_height)
        video_filter = f"{scale_filter},{crop_filter},setsar=1"

        expected_duration = 0.0
        resolved_video_files: list[str] = []
        logger.info(f"Input videos for concatenation:")

        for i, video_file in enumerate(video_files):
            abs_path = str(Path(video_file).resolve())
            resolved_video_files.append(abs_path)

            try:
                input_info = await self.get_video_info(str(video_file))
                input_duration = input_info["duration"]
                expected_duration += input_duration
                logger.info(f"  [{i+1}] {Path(video_file).name}: {input_duration:.2f}s")
            except Exception as e:
                logger.warning(f"  [{i+1}] {Path(video_file).name}: Could not get duration - {e}")

        logger.info(f"Expected output duration: {expected_duration:.2f}s (sum of {len(video_files)} videos)")

        cmd = [self.ffmpeg_path, "-y"]
        for video_file in resolved_video_files:
            cmd.extend(["-i", video_file])

        filter_complex = _build_concat_filter(resolved_video_files, video_filter, remove_audio)

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", self.video_codec,
            "-profile:v", "main",
            "-level", "4.0",
            "-g", "30",
            "-bf", "2",
            "-preset", self.preset,
            "-crf", str(self.crf),
        ])

        if remove_audio:
            cmd.append("-an")
        else:
            cmd.extend(["-map", "[aout]", "-c:a", self.audio_codec, "-b:a", "192k"])

        cmd.append(str(output_path))

        logger.info(f"Running FFmpeg concatenation...")

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=1800, operation="video concatenation",
            details={"video_count": len(resolved_video_files)},
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg error: {error_msg}")
            raise FFmpegFailedException(
                operation="video concatenation",
                stderr=error_msg,
                returncode=returncode,
                details={"video_count": len(resolved_video_files)},
            )

        await self._validate_concat_duration(output_path, expected_duration, video_files)

        logger.info(f"Video concatenated successfully: {output_path}")
        return output_path

    async def _ensure_compatibility(self, video_files: list[str]) -> list[str]:
        """Ensure all videos are compatible for concatenation."""
        logger.info(f"Ensuring video compatibility before concatenation...")

        from ..services.video_compatibility_fixer import VideoCompatibilityFixer

        fixer = VideoCompatibilityFixer()
        try:
            video_files_paths = await fixer.ensure_compatibility(
                video_paths=[Path(vf) for vf in video_files],
                output_dir=None,
                target_spec=None,
                force_reconvert=False,
            )
            video_files = [str(vf) for vf in video_files_paths]
            logger.info(f"Video compatibility ensured: {len(video_files)} videos ready (converted in-place)")
        except Exception as compat_error:
            logger.error(f"Failed to ensure video compatibility: {compat_error}", exc_info=True)
            raise

        logger.info(f"Validating video compatibility after fix...")

        from ..services.video_compatibility_validator import VideoCompatibilityValidator

        try:
            compat_result = await VideoCompatibilityValidator.validate_concat_compatibility(
                video_files=video_files,
                video_builder=self,
                strict=True,
                fps_tolerance=0.1,
            )
            logger.info(
                f"Compatibility check passed: all {compat_result['total_videos']} videos compatible",
                extra={
                    "reference_codec": compat_result["reference_video"]["codec"] if compat_result["reference_video"] else None,
                    "reference_fps": compat_result["reference_video"]["fps"] if compat_result["reference_video"] else None,
                    "reference_resolution": compat_result["reference_video"]["resolution"] if compat_result["reference_video"] else None,
                },
            )
        except Exception as compat_error:
            logger.error(f"Video compatibility check failed: {compat_error}", exc_info=True)
            raise

        return video_files

    async def _validate_concat_duration(
        self,
        output_path: str,
        expected_duration: float,
        video_files: list[str],
    ) -> None:
        """Validate concatenated video duration matches expected."""
        output_info = await self.get_video_info(str(output_path))
        actual_duration = output_info["duration"]

        logger.info(f"Concatenation result:")
        logger.info(f"  Expected: {expected_duration:.2f}s")
        logger.info(f"  Actual: {actual_duration:.2f}s")
        logger.info(f"  Difference: {abs(actual_duration - expected_duration):.2f}s")

        tolerance = 2.0
        if abs(actual_duration - expected_duration) > tolerance:
            logger.error(
                f"CONCATENATION BUG DETECTED! "
                f"Actual duration ({actual_duration:.2f}s) differs from expected "
                f"({expected_duration:.2f}s) by {abs(actual_duration - expected_duration):.2f}s"
            )
            raise ConcatenationException(
                video_count=len(video_files),
                expected_duration=expected_duration,
                actual_duration=actual_duration,
                reason=f"Duration mismatch: expected {expected_duration:.2f}s, got {actual_duration:.2f}s",
                details={
                    "difference": actual_duration - expected_duration,
                    "tolerance": tolerance,
                },
            )

    async def crop_video_for_validation(self,
                                        video_path: str,
                                        output_path: str,
                                        aspect_ratio: str = "9:16",
                                        crop_position: str = "center") -> str:
        """Aplica crop no video ANTES da validacao OCR."""
        logger.info(f"Cropping video for OCR validation")
        logger.info(f"   Input: {video_path}")
        logger.info(f"   Output: {output_path}")
        logger.info(f"   Aspect ratio: {aspect_ratio}")
        logger.info(f"   Crop position: {crop_position}")

        if aspect_ratio not in ASPECT_MAP:
            raise VideoInvalidResolutionException(
                aspect_ratio=aspect_ratio,
                valid_ratios=list(ASPECT_MAP.keys()),
            )

        target_width, target_height = ASPECT_MAP[aspect_ratio]

        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase"
        crop_filter = _build_crop_filter(crop_position, target_width, target_height)
        video_filter = f"{scale_filter},{crop_filter},setsar=1"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-vf", video_filter,
            "-an",
            "-c:v", self.video_codec,
            "-preset", "ultrafast",
            "-crf", "28",
            str(output_path),
        ]

        logger.info(f"Running FFmpeg crop...")

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=300, operation="video crop for validation",
            details={"video_path": str(video_path)},
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg crop error: {error_msg}")
            raise VideoEncodingException(
                operation="video crop for validation",
                reason=error_msg,
                details={"video_path": str(video_path), "crop_filter": crop_filter},
            )

        logger.info(f"Video cropped for validation: {output_path}")
        return output_path

    async def add_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Adiciona audio a um video."""
        logger.info(f"Adding audio to video")

        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", self.audio_codec,
            "-profile:a", "aac_low",
            "-b:a", "192k",
            str(output_path),
        ]

        logger.info(f"Running FFmpeg audio addition...")

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=600, operation="audio addition to video",
            details={"video_path": str(video_path), "audio_path": str(audio_path)},
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg error: {error_msg}")
            raise VideoEncodingException(
                operation="audio addition to video",
                reason=error_msg,
                details={"video_path": str(video_path), "audio_path": str(audio_path), "return_code": returncode},
            )

        logger.info(f"Audio added: {output_path}")
        return output_path

    async def burn_subtitles(self, video_path: str, subtitle_path: str,
                             output_path: str, style: str = "dynamic") -> str:
        """Adiciona legendas hard-coded ao video."""
        logger.info(f"Burning subtitles (style: {style})")

        video_path_obj = Path(video_path).resolve()
        subtitle_path_obj = Path(subtitle_path).resolve()
        output_path_obj = Path(output_path).resolve()
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        validate_srt(str(subtitle_path_obj))

        input_info = await self.get_video_info(str(video_path_obj))
        input_duration = input_info["duration"]
        logger.info(f"Input video duration: {input_duration:.2f}s")

        subtitle_style = get_subtitle_style(style)

        subtitle_path_escaped = str(subtitle_path_obj).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path_obj),
            "-vf", f"subtitles={subtitle_path_escaped}:force_style='{subtitle_style}'",
            "-c:a", "copy",
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-y",
            str(output_path_obj),
        ]

        logger.info(f"Running FFmpeg subtitle burn-in...")

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=900, operation="subtitle burn-in",
            details={"video_path": str(video_path), "subtitle_path": str(subtitle_path)},
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg error: {error_msg}")
            raise VideoEncodingException(
                operation="subtitle burn-in",
                reason=error_msg,
                details={"video_path": str(video_path), "subtitle_path": str(subtitle_path), "return_code": returncode},
            )

        output_info = await self.get_video_info(str(output_path_obj))
        output_duration = output_info["duration"]

        logger.info(f"Subtitle burn result:")
        logger.info(f"  Input: {input_duration:.2f}s")
        logger.info(f"  Output: {output_duration:.2f}s")

        if abs(output_duration - input_duration) > 1.0:
            logger.warning(
                f"Duration changed after subtitle burn: "
                f"{input_duration:.2f}s -> {output_duration:.2f}s "
                f"(diff: {abs(output_duration - input_duration):.2f}s)"
            )

        logger.info(f"Subtitles burned: {output_path_obj}")
        return str(output_path_obj)

    async def create_title_card(
        self,
        first_frame_path: str,
        text: str,
        output_path: str,
        duration: float = 0.2,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Cria title card curto com texto sobre primeira imagem."""
        logger.info(f"Creating title card ({duration}s)")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        escaped_text = text.replace("'", "\\'").replace(":", "\\:").replace('"', '\\"')

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-loop", "1",
            "-i", first_frame_path,
            "-t", str(duration),
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"drawtext=text='{escaped_text}'"
                f":fontsize=48:fontcolor=white:borderw=3:bordercolor=black"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", "libx264",
            "-profile:v", "main",
            "-level", "4.0",
            "-g", "30",
            "-bf", "2",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path,
        ]

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=60, operation="title card creation",
            details={"output": output_path},
        )

        if returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise FFmpegFailedException(
                operation="title card creation",
                stderr=error_msg,
                returncode=returncode,
                details={"output": output_path},
            )

        logger.info(f"Title card created: {output_path}")
        return output_path

    async def concat_with_transitions(
        self,
        segments: list[str],
        output_path: str,
        transition: str = "circleopen",
        transition_duration: float = 0.2,
        aspect_ratio: str = "9:16",
    ) -> str:
        """Concatena segmentos com transicoes xfade."""
        if len(segments) < 2:
            raise ConcatenationException(
                video_count=len(segments),
                expected_duration=0,
                actual_duration=0,
                reason="Need at least 2 segments for transitions",
            )

        logger.info(f"Concatenating {len(segments)} segments with transitions")

        target_w, target_h = ASPECT_MAP.get(aspect_ratio, (1080, 1920))

        cmd = [self.ffmpeg_path, "-y"]
        for seg in segments:
            cmd.extend(["-i", seg])

        filter_complex = await self._build_xfade_chain(
            segments, transition, transition_duration, target_w, target_h,
        )

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]"])

        if len(segments) >= 2:
            cmd.extend(["-map", "1:a?", "-c:a", self.audio_codec, "-profile:a", "aac_low", "-b:a", "192k"])
            cmd.extend(["-shortest"])

        cmd.append(output_path)

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=300, operation="concat with transitions",
            details={"segment_count": len(segments)},
        )

        if returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg concat with transitions error: {error_msg}")
            raise FFmpegFailedException(
                operation="concat with transitions",
                stderr=error_msg,
                returncode=returncode,
                details={"segment_count": len(segments)},
            )

        logger.info(f"Concatenated with transitions: {output_path}")
        return output_path

    async def _build_xfade_chain(
        self,
        segments: list[str],
        transition: str,
        transition_duration: float,
        target_w: int,
        target_h: int,
    ) -> str:
        """Build xfade filter chain for segment concatenation."""
        n = len(segments)
        filter_parts: list[str] = []

        for i in range(n):
            filter_parts.append(
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},setsar=1,format=yuv420p[v{i}]"
            )

        if n == 2:
            offset = 0
            filter_parts.append(
                f"[v0][v1]xfade=transition={transition}:duration={transition_duration}:offset={offset}[vout]"
            )
        else:
            filter_parts.append(
                f"[v0][v1]xfade=transition={transition}:duration={transition_duration}:offset=0[xf0]"
            )
            info = await self.get_video_info(segments[0])
            cumulative_offset = info["duration"] - transition_duration

            for i in range(2, n):
                prev_label = f"xf{i - 2}"
                info = await self.get_video_info(segments[i - 1])
                seg_duration = info["duration"]
                if i < n - 1:
                    cumulative_offset += seg_duration - transition_duration
                    out_label = f"xf{i - 1}"
                    filter_parts.append(
                        f"[{prev_label}][v{i}]xfade=transition=fade:duration={transition_duration}:offset={cumulative_offset}[{out_label}]"
                    )
                else:
                    cumulative_offset += seg_duration - transition_duration
                    filter_parts.append(
                        f"[{prev_label}][v{i}]xfade=transition=fade:duration={transition_duration}:offset={cumulative_offset}[vout]"
                    )

        return ";".join(filter_parts)

    async def trim_video(self, video_path: str, output_path: str,
                         max_duration: float) -> str:
        """Trim video para duracao maxima especificada."""
        logger.info(f"Trimming video to {max_duration:.2f}s (re-encode mode for precision)")

        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-t", str(max_duration),
            "-c:v", "libx264",
            "-profile:v", "main",
            "-level", "4.0",
            "-g", "30",
            "-bf", "2",
            "-c:a", "aac",
            "-profile:a", "aac_low",
            "-preset", "fast",
            "-crf", "23",
            "-map", "0:v:0",
            "-map", "0:a:0",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path),
        ]

        logger.info(f"Running FFmpeg trim (re-encode for precision)...")

        returncode, stdout, stderr = await run_ffmpeg_cmd(
            cmd=cmd, timeout=600, operation="video trim",
            details={"video_path": str(video_path), "max_duration": max_duration},
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFmpeg trim error: {error_msg}")
            raise VideoEncodingException(
                operation="video trim",
                reason=error_msg,
                details={"video_path": str(video_path), "max_duration": max_duration, "return_code": returncode},
            )

        logger.info(f"Video trimmed to {max_duration:.2f}s: {output_path}")
        return output_path

    async def get_video_info(self, video_path: str) -> dict[str, Any]:
        """Extrai informacoes do video usando ffprobe."""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        returncode, stdout, stderr = await run_ffprobe_cmd(
            cmd=cmd, timeout=30, operation="video info extraction",
            video_path=str(video_path),
        )

        if returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"FFprobe error: {error_msg}")
            raise FFprobeFailedException(
                video_path=str(video_path),
                stderr=error_msg,
                returncode=returncode,
            )

        try:
            info = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason="Failed to parse ffprobe JSON output",
                details={"json_error": str(e)},
            )

        video_stream = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)

        if not video_stream:
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason="No video stream found in file",
            )

        result: dict[str, Any] = {
            "duration": float(info["format"]["duration"]),
            "size": int(info["format"]["size"]),
            "resolution": f"{video_stream['width']}x{video_stream['height']}",
            "width": video_stream["width"],
            "height": video_stream["height"],
            "codec": video_stream["codec_name"],
        }

        if "r_frame_rate" in video_stream:
            try:
                fps_parts = video_stream["r_frame_rate"].split("/")
                if len(fps_parts) == 2:
                    result["fps"] = int(fps_parts[0]) / int(fps_parts[1])
                else:
                    result["fps"] = float(fps_parts[0]) if fps_parts else 30
            except (ValueError, ZeroDivisionError):
                result["fps"] = 30
        else:
            result["fps"] = 30

        return result

    async def get_audio_duration(self, audio_path: str) -> float:
        """Obtém duracao de um arquivo de audio."""
        duration = await get_audio_duration_ffprobe(
            audio_path=str(audio_path),
            ffprobe_path=self.ffprobe_path,
        )
        logger.info(f"Audio duration: {duration:.2f}s")
        return duration
