"""Video assembly service using FFmpeg."""
import logging
import os
from typing import Optional

from app.core.config import settings
from app.core.models import NarrationSegment, OnScreenText
from app.infrastructure import ffmpeg_utils

logger = logging.getLogger(__name__)


class VideoAssembler:
    """Assemble final video from audio, images, and subtitles."""

    def _generate_srt(
        self,
        on_screen_text: list[OnScreenText],
        output_path: str,
    ) -> None:
        """Generate SRT subtitle file from on_screen_text."""
        sorted_text = sorted(on_screen_text, key=lambda x: x.t)

        with open(output_path, "w", encoding="utf-8") as f:
            for i, item in enumerate(sorted_text):
                start = self._format_srt_time(item.t)
                if i < len(sorted_text) - 1:
                    end = self._format_srt_time(sorted_text[i + 1].t - 0.1)
                else:
                    end = self._format_srt_time(item.t + 5.0)

                f.write(f"{i + 1}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{item.text}\n\n")

    def _format_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format."""
        if seconds < 0:
            seconds = 0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _calculate_scene_durations(
        self,
        narration: list[NarrationSegment],
        audio_duration: float,
    ) -> list[float]:
        """Calculate duration for each scene based on narration timestamps."""
        sorted_segs = sorted(narration, key=lambda s: s.t)
        durations = []

        for i in range(len(sorted_segs)):
            start = sorted_segs[i].t
            if i < len(sorted_segs) - 1:
                end = sorted_segs[i + 1].t
            else:
                end = audio_duration
            durations.append(max(end - start, 0.5))

        return durations

    async def assemble(
        self,
        audio_path: str,
        image_paths: list[str],
        narration: list[NarrationSegment],
        on_screen_text: list[OnScreenText],
        output_dir: str,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        zoom_style: str = "random",
        crossfade_duration: float = 0.5,
    ) -> str:
        """Assemble final video. Returns path to completed video."""
        audio_duration = await ffmpeg_utils.get_audio_duration(audio_path)
        scene_durations = self._calculate_scene_durations(narration, audio_duration)

        logger.info(f"Assembling video: {len(image_paths)} scenes, {audio_duration:.1f}s audio")

        segment_paths = []
        for i, (img_path, dur) in enumerate(zip(image_paths, scene_durations)):
            segment_path = os.path.join(output_dir, f"segment_{i}.mp4")
            logger.info(f"Creating segment {i}: {dur:.1f}s")
            await ffmpeg_utils.create_segment(
                image_path=img_path,
                output_path=segment_path,
                duration=dur,
                width=width,
                height=height,
                fps=fps,
                zoom_style=zoom_style,
            )
            segment_paths.append(segment_path)

        concat_path = os.path.join(output_dir, "video_concat.mp4")
        logger.info("Concatenating segments with crossfade")
        await ffmpeg_utils.concat_segments(
            segment_paths=segment_paths,
            output_path=concat_path,
            crossfade_duration=crossfade_duration,
        )

        audio_video_path = os.path.join(output_dir, "video_audio.mp4")
        logger.info("Adding audio track")
        await ffmpeg_utils.add_audio(
            video_path=concat_path,
            audio_path=audio_path,
            output_path=audio_video_path,
        )

        if on_screen_text:
            srt_path = os.path.join(output_dir, "subtitles.srt")
            self._generate_srt(on_screen_text, srt_path)

            subtitled_path = os.path.join(output_dir, "video_subtitled.mp4")
            logger.info("Burning subtitles")
            await ffmpeg_utils.burn_subtitles(
                video_path=audio_video_path,
                srt_path=srt_path,
                output_path=subtitled_path,
            )
            final_source = subtitled_path
        else:
            final_source = audio_video_path

        final_path = os.path.join(output_dir, "final.mp4")
        logger.info("Trimming to audio duration")
        await ffmpeg_utils.trim_to_duration(
            video_path=final_source,
            duration=audio_duration,
            output_path=final_path,
        )

        self._cleanup_temp(output_dir, final_path)
        logger.info(f"Video assembled: {final_path}")
        return final_path

    def _cleanup_temp(self, output_dir: str, keep_file: str) -> None:
        """Remove temporary files, keeping the final output."""
        for f in os.listdir(output_dir):
            if f.startswith("segment_") or f.startswith("audio_chunk_"):
                os.remove(os.path.join(output_dir, f))
        for name in ["video_concat.mp4", "video_audio.mp4", "video_subtitled.mp4", "subtitles.srt"]:
            path = os.path.join(output_dir, name)
            if os.path.exists(path) and path != keep_file:
                os.remove(path)
