"""
FinalCompositionStage - Add audio, optional title card, and burn subtitles

🎯 Responsibilities:
    - Create title card if hook_text is provided (FIX-ERROS Fase 1)
    - Add audio track to video
    - Conditionally burn subtitles (FIX-ERROS Fase 2)
    - Create final video file
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode
from common.log_utils import get_logger

logger = get_logger(__name__)

class FinalCompositionStage(JobStage):
    """Stage 7: Final composition (optional title card + audio + optional subtitles)"""
    
    def __init__(self, video_builder) -> None:
        super().__init__(
            name="final_composition",
            progress_start=85.0,
            progress_end=92.0
        )
        self.video_builder = video_builder
    
    def validate(self, context: StageContext) -> None:
        """Validate all required files exist"""
        if not context.temp_video_path or not context.temp_video_path.exists():
            raise VideoProcessingException(
                "Temporary video file not found",
                error_code=ErrorCode.VIDEO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
        
        if not context.audio_path or not context.audio_path.exists():
            raise VideoProcessingException(
                "Audio file not found",
                error_code=ErrorCode.AUDIO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
        
        # FIX-ERROS Fase 2: subtitle is OPTIONAL — only required if burn_subtitles is True
        if context.burn_subtitles:
            if not context.subtitle_path or not context.subtitle_path.exists():
                raise VideoProcessingException(
                    "Subtitle file not found (burn_subtitles=True but no subtitle file)",
                    error_code=ErrorCode.SUBTITLE_FILE_NOT_FOUND,
                    job_id=context.job_id,
                )
    
    async def execute(self, context: StageContext) -> dict[str, Any]:
        """
        Compose final video with optional title card, audio, and optional subtitles.
        
        Flow:
            1. (Optional) Create title card from first frame + hook_text
            2. (Optional) Concat title card + content with circleopen transition
            3. Add audio to base video
            4. (Optional) Burn subtitles
        """
        job_dir = Path(context.settings['temp_dir']) / context.job_id
        base_video_path = context.temp_video_path

        # ── Fase 1: Title card + circleopen transition ──────────────────────
        if context.hook_text:
            logger.info(f"🎬 Fase 1: Creating title card with hook: '{context.hook_text}'")

            # 1a. Extract first frame as image
            first_frame_path = str(job_dir / "first_frame.jpg")
            await self._extract_first_frame(
                video_path=str(context.temp_video_path),
                output_path=first_frame_path,
            )

            # 1b. Create 0.2s title card
            title_card_path = str(job_dir / "title_card.mp4")
            await self.video_builder.create_title_card(
                first_frame_path=first_frame_path,
                text=context.hook_text,
                output_path=title_card_path,
                duration=0.2,
            )

            # 1c. Concat title card + content with circleopen transition
            concatenated_path = str(job_dir / "video_with_title.mp4")
            await self.video_builder.concat_with_transitions(
                segments=[title_card_path, str(context.temp_video_path)],
                output_path=concatenated_path,
                transition="circleopen",
                transition_duration=0.2,
                aspect_ratio=context.aspect_ratio,
            )

            base_video_path = Path(concatenated_path)
            logger.info(f"✅ Title card created and concatenated")
        else:
            logger.info(f"⏭️  No hook_text — skipping title card")

        # ── Add audio ───────────────────────────────────────────────────────
        video_with_audio_path = Path(context.settings['temp_dir']) / context.job_id / "video_with_audio.mp4"
        
        logger.info(f"🎵 Adding audio...")
        await self.video_builder.add_audio(
            video_path=str(base_video_path),
            audio_path=str(context.audio_path),
            output_path=str(video_with_audio_path)
        )
        logger.info(f"✅ Audio added")
        
        # ── Fase 2: Conditional subtitle burn ───────────────────────────────
        if context.burn_subtitles and context.subtitle_path and context.subtitle_path.exists():
            final_video_path = Path(context.settings['output_dir']) / f"{context.job_id}_final.mp4"
            
            logger.info(f"📝 Burning subtitles...")
            style = context.subtitle_style if isinstance(context.subtitle_style, str) else "dynamic"
            await self.video_builder.burn_subtitles(
                video_path=str(video_with_audio_path),
                subtitle_path=str(context.subtitle_path),
                output_path=str(final_video_path),
                style=style,
            )
            logger.info(f"✅ Subtitles burned")
        else:
            # No subtitle burn — use video_with_audio as final
            final_video_path = Path(context.settings['output_dir']) / f"{context.job_id}_final.mp4"
            logger.info(f"⏭️  Skipping subtitle burn (burn_subtitles={context.burn_subtitles})")

            import shutil
            shutil.copy2(str(video_with_audio_path), str(final_video_path))

        logger.info(f"✅ Final video created: {final_video_path}")
        
        # Update context
        context.video_with_audio_path = video_with_audio_path
        context.final_video_path = final_video_path
        
        return {
            'video_with_audio_path': str(video_with_audio_path),
            'final_video_path': str(final_video_path),
            'title_card': context.hook_text is not None,
            'burn_subtitles': context.burn_subtitles,
        }

    async def _extract_first_frame(self, video_path: str, output_path: str) -> str:
        """Extract first frame as JPEG image for title card background."""
        logger.info(f"🖼️  Extracting first frame from {video_path}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.video_builder.ffmpeg_path,
            "-y",
            "-i", video_path,
            "-vf", "select=eq(n\\,0)",
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]

        try:
            from ...infrastructure.subprocess_utils import run_subprocess_with_timeout

            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=30,
                check=False,
                capture_output=True,
            )

            if returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.warning(f"⚠️ Frame extraction failed: {error_msg}")
                # Fallback: create a black frame
                await self._create_black_frame(output_path)

            return output_path

        except Exception as e:
            logger.warning(f"⚠️ Frame extraction error: {e}, creating black frame")
            await self._create_black_frame(output_path)
            return output_path

    async def _create_black_frame(self, output_path: str) -> str:
        """Create a black frame as fallback for title card."""
        cmd = [
            self.video_builder.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1080x1920:d=0.033",
            "-vframes", "1",
            output_path,
        ]

        from ...infrastructure.subprocess_utils import run_subprocess_with_timeout
        await run_subprocess_with_timeout(
            cmd=cmd, timeout=10, check=False, capture_output=True,
        )
        return output_path
    
    async def compensate(self, context: StageContext) -> None:
        """Delete intermediate and final video files"""
        for attr in ('video_with_audio_path', 'final_video_path'):
            path = getattr(context, attr, None)
            if path and Path(path).exists():
                logger.info(f"↩️  Deleting {attr}: {path}")
                Path(path).unlink()
