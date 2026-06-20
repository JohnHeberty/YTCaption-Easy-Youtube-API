"""Video assembly service using FFmpeg."""
import os
from common.log_utils import get_logger
import random
from typing import Optional

from app.core.config import settings
from app.core.constants import TRANSITIONS
from app.core.models import NarrationSegment
from app.infrastructure import ffmpeg_utils

logger = get_logger(__name__)

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
        MAX_SEGMENTS = 12
        num_scenes_needed = min(num_scenes_needed, MAX_SEGMENTS)
        if num_scenes_needed < 1:
            num_scenes_needed = 1
        base_dur = audio_duration / num_scenes_needed
        durations = [base_dur] * num_scenes_needed
        # Fix floating point: last scene gets the remainder
        durations[-1] = audio_duration - base_dur * (num_scenes_needed - 1)
        return durations

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
    ) -> str:
        """Assemble final video. Returns path to completed video.

        Images are looped cyclically to cover the full audio duration.
        """
        audio_duration = await ffmpeg_utils.get_audio_duration(audio_path)

        # Calculate average per-scene duration from narration timestamps
        sorted_segs = sorted(narration, key=lambda s: s.t)
        if len(sorted_segs) >= 2:
            total_span = sorted_segs[-1].t - sorted_segs[0].t
            per_scene_duration = total_span / (len(sorted_segs) - 1)
        else:
            per_scene_duration = audio_duration

        # Clamp per_scene_duration to reasonable range
        per_scene_duration = max(per_scene_duration, 3.0)
        per_scene_duration = min(per_scene_duration, 15.0)

        # How many scenes do we need to cover the full audio?
        num_scenes_needed = max(1, int(audio_duration / per_scene_duration) + 1)

        scene_durations = self._calculate_scene_durations(
            audio_duration, num_scenes_needed
        )
        num_scenes_needed = len(scene_durations)

        title_duration = settings.title_card_duration
        title_path = None
        if hook_text:
            title_path = os.path.join(output_dir, "title_card.mp4")
            logger.info(f"Creating title card: {title_duration}s")
            await ffmpeg_utils.create_title_card(
                image_path=image_paths[0],
                output_path=title_path,
                hook_text=hook_text,
                duration=title_duration,
                width=width,
                height=height,
                fps=fps,
            )

        # Loop images cyclically to fill all scenes
        cycled_images = [image_paths[i % len(image_paths)] for i in range(num_scenes_needed)]

        logger.info(
            f"Assembling video: {len(image_paths)} source images → {num_scenes_needed} scenes "
            f"(per_scene={per_scene_duration:.1f}s), {audio_duration:.1f}s audio, title={title_duration:.1f}s"
        )

        segment_paths = []
        if title_path:
            segment_paths.append(title_path)

        # Alternating zoom_in/zoom_out
        if zoom_style == "random":
            chosen_seq = random.choice(_STYLE_SEQUENCES)
        else:
            chosen_seq = [zoom_style]
        logger.info(f"Style sequence: {chosen_seq}")

        for i, (img_path, dur) in enumerate(zip(cycled_images, scene_durations)):
            segment_path = os.path.join(output_dir, f"segment_{i}.mp4")
            scene_style = chosen_seq[i % len(chosen_seq)]
            logger.info(f"Creating segment {i}: {dur:.1f}s, style={scene_style}")
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

        concat_path = os.path.join(output_dir, "video_concat.mp4")

        # Pick random transitions for variety — one per segment pair
        first_xfade = random.choice(["circleopen", "dissolve", "radial", "zoomin", "smoothleft"])
        num_transitions = len(segment_paths) - 1
        transition_list = [first_xfade] + [random.choice(TRANSITIONS) for _ in range(num_transitions - 1)]

        if len(segment_paths) <= 8:
            # Fits in one xfade batch
            logger.info(f"Concatenating {len(segment_paths)} segments with crossfade transitions: {transition_list}")
            await ffmpeg_utils.concat_segments(
                segment_paths=segment_paths,
                output_path=concat_path,
                crossfade_duration=crossfade_duration,
                transitions=transition_list,
            )
        else:
            # Too many for one xfade — batch into groups of 8 with xfade each
            logger.info(
                f"Concatenating {len(segment_paths)} segments in batches of 8 "
                f"(transitions within batches, hard cut between batches)"
            )
            await ffmpeg_utils.concat_batched(
                segment_paths=segment_paths,
                output_path=concat_path,
                crossfade_duration=crossfade_duration,
                transitions=transition_list,
                batch_size=8,
            )

        padded_audio_path = os.path.join(output_dir, "audio_padded.wav")
        await self._pad_audio_start(audio_path, padded_audio_path, title_duration)

        audio_video_path = os.path.join(output_dir, "video_audio.mp4")
        logger.info("Adding audio track")
        await ffmpeg_utils.add_audio(
            video_path=concat_path,
            audio_path=padded_audio_path,
            output_path=audio_video_path,
        )

        # Get actual padded audio duration for trimming
        padded_duration = await ffmpeg_utils.get_audio_duration(padded_audio_path)
        final_name = f"{job_id}_final.mp4" if job_id else "final.mp4"
        final_path = os.path.join(output_dir, final_name)
        logger.info("Trimming to padded audio duration: %.1fs", padded_duration)
        await ffmpeg_utils.trim_to_duration(
            video_path=audio_video_path,
            duration=padded_duration,
            output_path=final_path,
        )

        logger.info(f"Video assembled: {final_path}")
        return final_path

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

        import asyncio

        # Detect source audio properties
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
