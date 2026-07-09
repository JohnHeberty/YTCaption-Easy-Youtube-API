"""Video assembly service using FFmpeg."""
from __future__ import annotations

import asyncio
import os
import random
from typing import Any

from common.log_utils import get_logger

from app.core.config import settings
from app.core.constants import CAMERA_MOVEMENT_MAP, TRANSITIONS, TRANSITION_MAP
from app.core.models import NarrationSegment, SceneSuggestion
from app.infrastructure import ffmpeg_utils

logger = get_logger(__name__)

MAX_SEGMENTS = 12
MIN_SCENE_DURATION = 3.0
MAX_SCENE_DURATION = 15.0
MAX_XFAD_BATCH_SIZE = 8

# Alternating zoom styles — alternates between zoom_in and zoom_out
_STYLE_SEQUENCES = [
    ["zoom_in", "zoom_out"],
    ["zoom_out", "zoom_in"],
]


class VideoAssembler:
    """Assemble final video from audio, images, and title card."""

    def _calculate_scene_durations(
        self,
        audio_duration: float,
        num_scenes_needed: int,
    ) -> list[float]:
        """Calculate equal durations per scene to cover the full audio.

        Caps at MAX_SEGMENTS scenes. Last segment absorbs any remainder.
        """
        num_scenes_needed = min(num_scenes_needed, MAX_SEGMENTS)
        if num_scenes_needed < 1:
            num_scenes_needed = 1
        base_dur = audio_duration / num_scenes_needed
        durations = [base_dur] * num_scenes_needed
        # Fix floating point: last scene gets the remainder
        durations[-1] = audio_duration - base_dur * (num_scenes_needed - 1)
        return durations

    def _build_scene_zoom_styles(
        self,
        scene_suggestions: list[SceneSuggestion] | None,
        num_scenes: int,
        image_paths: list[str],
        default_zoom_style: str,
    ) -> list[str]:
        """Build per-scene zoom styles from scene_suggestions camera_movement.

        Maps camera_movement values to Ken Burns zoom styles:
        - "static" → "static" (no zoom)
        - "slow_push_in" → "zoom_in"
        - "slow_pull_out" → "zoom_out"
        - None/missing → use default_zoom_style or random
        """
        styles: list[str] = []
        for i in range(num_scenes):
            # Get scene suggestion for this image (cycled)
            scene_idx = i % len(image_paths) if image_paths else i
            if scene_suggestions and scene_idx < len(scene_suggestions):
                cam_move = scene_suggestions[scene_idx].camera_movement
                if cam_move and cam_move in CAMERA_MOVEMENT_MAP:
                    mapped = CAMERA_MOVEMENT_MAP[cam_move]
                    if mapped == "random":
                        styles.append(random.choice(["zoom_in", "zoom_out"]))
                    else:
                        styles.append(mapped)
                    continue

            # Fallback to default or alternating
            if default_zoom_style == "random":
                styles.append(random.choice(["zoom_in", "zoom_out"]))
            else:
                styles.append(default_zoom_style)

        return styles

    def _build_scene_transitions(
        self,
        scene_suggestions: list[SceneSuggestion] | None,
        num_scenes: int,
        image_paths: list[str],
    ) -> list[str | None]:
        """Build per-scene transitions from scene_suggestions.

        Returns list of transition names (or None for hard cuts).
        Index i = transition AFTER scene i (len = num_scenes - 1).
        """
        transitions: list[str | None] = []
        for i in range(num_scenes - 1):
            scene_idx = i % len(image_paths) if image_paths else i
            if scene_suggestions and scene_idx < len(scene_suggestions):
                raw_trans = scene_suggestions[scene_idx].transition
                if raw_trans:
                    # Check if it's a known mapping from upstream JSON
                    if raw_trans in TRANSITION_MAP:
                        mapped = TRANSITION_MAP[raw_trans]
                        transitions.append(mapped)  # None = hard cut
                        continue
                    # Otherwise treat as direct FFmpeg xfade name
                    transitions.append(raw_trans)
                    continue

            # Fallback: random transition
            transitions.append(random.choice(TRANSITIONS))

        return transitions

    async def assemble(
        self,
        audio_path: str,
        image_paths: list[str],
        narration: list[NarrationSegment],
        output_dir: str,
        job_id: str = "",
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        zoom_style: str = "random",
        crossfade_duration: float = 0.5,
        hook_text: str = "",
        on_screen_text: list[dict[str, Any]] | None = None,
        scene_suggestions: list[SceneSuggestion] | None = None,
    ) -> str:
        """Assemble final video. Returns path to completed video.

        Images are looped cyclically to cover the full audio duration.
        """
        if not image_paths:
            raise ValueError("No images provided for video assembly")

        audio_duration = await ffmpeg_utils.get_audio_duration(audio_path)

        # Calculate average per-scene duration from narration timestamps
        sorted_segs = sorted(narration, key=lambda s: s.t)
        if len(sorted_segs) >= 2:
            total_span = sorted_segs[-1].t - sorted_segs[0].t
            per_scene_duration = total_span / (len(sorted_segs) - 1)
        else:
            per_scene_duration = audio_duration

        # Clamp per_scene_duration to reasonable range
        per_scene_duration = max(per_scene_duration, MIN_SCENE_DURATION)
        per_scene_duration = min(per_scene_duration, MAX_SCENE_DURATION)

        # How many scenes do we need to cover the full audio?
        num_scenes_needed = max(1, int(audio_duration / per_scene_duration) + 1)

        scene_durations = self._calculate_scene_durations(
            audio_duration, num_scenes_needed
        )
        num_scenes_needed = len(scene_durations)

        title_duration = settings.title_card_duration
        title_path: str | None = None
        if hook_text:
            title_path = os.path.join(output_dir, "title_card.mp4")
            logger.info("Creating title card: %.1fs", title_duration)
            await ffmpeg_utils.create_title_card(
                image_path=image_paths[0],
                output_path=title_path,
                duration=title_duration,
                width=width,
                height=height,
                fps=fps,
            )

        chosen_seq = random.choice(_STYLE_SEQUENCES)

        # Build per-scene zoom styles from scene_suggestions camera_movement
        scene_zoom_styles = self._build_scene_zoom_styles(
            scene_suggestions, num_scenes_needed, image_paths, zoom_style
        )

        # Build per-scene transitions from scene_suggestions
        scene_transitions = self._build_scene_transitions(
            scene_suggestions, num_scenes_needed, image_paths
        )

        logger.info(
            "Assembling video: %d source images → %d scenes "
            "(per_scene=%.1fs), %.1fs audio, title=%.1fs, zoom_styles=%s, transitions=%s",
            len(image_paths), num_scenes_needed,
            per_scene_duration, audio_duration, title_duration,
            scene_zoom_styles, scene_transitions,
        )

        segment_paths = await self._create_segments(
            image_paths, output_dir, scene_durations, width, height, fps, scene_zoom_styles
        )

        concat_path = os.path.join(output_dir, "video_concat.mp4")
        await self._concatenate(concat_path, segment_paths, crossfade_duration, scene_transitions)

        padded_audio_path = os.path.join(output_dir, "audio_padded.wav")
        final_path = await self._merge_audio_video(
            audio_path, padded_audio_path, concat_path,
            title_duration, output_dir, job_id,
            on_screen_text=on_screen_text,
        )

        logger.info("Video assembled: %s", final_path)
        return final_path

    async def _create_segments(
        self, image_paths: list[str], output_dir: str, scene_durations: list[float],
        width: int, height: int, fps: int, scene_zoom_styles: list[str],
    ) -> list[str]:
        """Create individual video segments from images."""
        cycled_images = [image_paths[i % len(image_paths)] for i in range(len(scene_durations))]
        segment_paths: list[str] = []
        for i, (img_path, dur) in enumerate(zip(cycled_images, scene_durations)):
            segment_path = os.path.join(output_dir, f"segment_{i}.mp4")
            scene_style = scene_zoom_styles[i] if i < len(scene_zoom_styles) else "random"
            logger.info("Creating segment %d: %.1fs, style=%s", i, dur, scene_style)
            await ffmpeg_utils.create_segment(
                image_path=img_path,
                output_path=segment_path,
                duration=dur,
                width=width,
                height=height,
                fps=fps,
                zoom_style=scene_style,
            )
            segment_paths.append(segment_path)
        return segment_paths

    async def _concatenate(
        self, concat_path: str, segment_paths: list[str], crossfade_duration: float,
        scene_transitions: list[str | None] | None = None,
    ) -> None:
        """Concatenate segments with crossfade transitions.

        Uses per-scene transitions from scene_suggestions when available.
        Falls back to random transitions for scenes without explicit transitions.
        """
        num_transitions = len(segment_paths) - 1
        transition_list: list[str] = []

        for i in range(num_transitions):
            # scene_transitions[i] is the transition AFTER scene i
            if scene_transitions and i < len(scene_transitions) and scene_transitions[i]:
                transition_list.append(scene_transitions[i])
            else:
                transition_list.append(random.choice(TRANSITIONS))

        if len(segment_paths) <= MAX_XFAD_BATCH_SIZE:
            logger.info("Concatenating %d segments with crossfade transitions: %s", len(segment_paths), transition_list)
            await ffmpeg_utils.concat_segments(
                segment_paths=segment_paths,
                output_path=concat_path,
                crossfade_duration=crossfade_duration,
                transitions=transition_list,
            )
        else:
            logger.info(
                "Concatenating %d segments in batches of %d "
                "(transitions within batches, hard cut between batches)",
                len(segment_paths), MAX_XFAD_BATCH_SIZE,
            )
            await ffmpeg_utils.concat_batched(
                segment_paths=segment_paths,
                output_path=concat_path,
                crossfade_duration=crossfade_duration,
                transitions=transition_list,
                batch_size=MAX_XFAD_BATCH_SIZE,
            )

    async def _merge_audio_video(
        self, audio_path: str, padded_audio_path: str, concat_path: str,
        title_duration: float, output_dir: str, job_id: str,
        on_screen_text: list[dict[str, Any]] | None = None,
    ) -> str:
        """Pad audio, add to video, render captions, and trim to final duration."""
        await self._pad_audio_start(audio_path, padded_audio_path, title_duration)

        audio_video_path = os.path.join(output_dir, "video_audio.mp4")
        logger.info("Adding audio track")
        await ffmpeg_utils.add_audio(
            video_path=concat_path,
            audio_path=padded_audio_path,
            output_path=audio_video_path,
        )

        # Render captions if provided
        if on_screen_text:
            captioned_path = os.path.join(output_dir, "video_captioned.mp4")
            logger.info("Rendering %d captions", len(on_screen_text))
            await ffmpeg_utils.render_captions(
                video_path=audio_video_path,
                output_path=captioned_path,
                captions=on_screen_text,
            )
            video_for_trim = captioned_path
        else:
            video_for_trim = audio_video_path

        padded_duration = await ffmpeg_utils.get_audio_duration(padded_audio_path)
        final_name = f"{job_id}_final.mp4" if job_id else "final.mp4"
        final_path = os.path.join(output_dir, final_name)
        logger.info("Trimming to padded audio duration: %.1fs", padded_duration)
        await ffmpeg_utils.trim_to_duration(
            video_path=video_for_trim,
            duration=padded_duration,
            output_path=final_path,
        )
        return final_path

    async def _probe_audio_properties(self, audio_path: str) -> tuple[str, str]:
        """Probe audio file for sample rate and channels. Returns (sample_rate, channel_layout)."""
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels",
            "-of", "csv=p=0",
            audio_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await probe.communicate()
        parts = stdout.decode().strip().split(",")
        sr = parts[0].strip() if parts else "24000"
        ch = int(parts[1].strip()) if len(parts) > 1 else 1
        cl = "stereo" if ch > 1 else "mono"
        return sr, cl

    async def _pad_audio_start(
        self, audio_path: str, output_path: str, silence_seconds: float
    ) -> None:
        """Prepend silence to audio track.

        Detects source audio sample rate and channels to generate matching
        silence, avoiding resampling artifacts (hiss/static) at the boundary.
        """
        if silence_seconds <= 0:
            import shutil
            shutil.copy2(audio_path, output_path)
            return

        sr, cl = await self._probe_audio_properties(audio_path)

        logger.info("Padding audio: silence at %s Hz %s for %.3fs", sr, cl, silence_seconds)

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sr}:cl={cl}:d={silence_seconds:.3f}",
            "-i", audio_path,
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg pad audio failed: {stderr.decode(errors='replace')}")
