"""
GenerateSubtitlesStage - Transcribe audio and generate word-by-word subtitles

🎯 Responsibilities:
    - Transcribe audio with word timestamps
    - Apply speech gating (VAD)
    - Generate SRT file with word-by-word captions
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import AudioProcessingException, ErrorCode
from common.log_utils import get_logger

logger = get_logger(__name__)

MAX_SUBTITLE_RETRIES = 5
MAX_BACKOFF_SECONDS = 300

class GenerateSubtitlesStage(JobStage):
    """Stage 6: Generate subtitles with VAD"""
    
    def __init__(self, api_client, subtitle_generator, vad_processor) -> None:
        """
        Initialize stage
        
        Args:
            api_client: APIClient for transcription
            subtitle_generator: SubtitleGenerator instance
            vad_processor: VAD processor function
        """
        super().__init__(
            name="generate_subtitles",
            progress_start=80.0,
            progress_end=85.0
        )
        self.api_client = api_client
        self.subtitle_generator = subtitle_generator
        self.vad_processor = vad_processor
    
    def validate(self, context: StageContext) -> None:
        """Validate audio path exists"""
        if not context.audio_path or not context.audio_path.exists():
            raise AudioProcessingException(
                "Audio file not found",
                error_code=ErrorCode.AUDIO_FILE_NOT_FOUND,
                job_id=context.job_id,
            )
    
    async def execute(self, context: StageContext) -> dict[str, Any]:
        """
        Generate subtitles with speech gating

        Returns:
            Dict with subtitle_path, cue_count, vad_status
        """
        logger.info(f"📝 Generating subtitles for {context.audio_path}")

        # 1. Transcribe audio with retry
        segments = await self._transcribe_with_retry(
            str(context.audio_path), context.subtitle_language
        )
        
        logger.info(f"📊 Transcription: {len(segments)} segments")
        
        # 2. Extract word-level cues
        raw_cues = self._extract_word_cues(segments)
        
        if not raw_cues:
            logger.error(f"❌ NO WORDS extracted from {len(segments)} segments!")
            raise AudioProcessingException(
                "No words extracted from transcription",
                error_code=ErrorCode.TRANSCRIPTION_FAILED,
                details={'segments_count': len(segments)},
                job_id=context.job_id,
            )
        
        logger.info(f"📊 Extracted {len(raw_cues)} word cues")
        
        # 3. Apply speech gating (VAD)
        logger.info(f"🎙️ Applying speech gating (VAD)...")
        
        try:
            gated_cues, vad_ok = self.vad_processor(str(context.audio_path), raw_cues)
            
            if vad_ok:
                logger.info(
                    f"✅ Speech gating OK: {len(gated_cues)}/{len(raw_cues)} cues (silero-vad)"
                )
            else:
                logger.warning(
                    f"⚠️ Speech gating fallback: {len(gated_cues)}/{len(raw_cues)} cues "
                    f"(webrtcvad/RMS)"
                )
            
            final_cues = gated_cues
            
        except Exception as e:
            logger.error(f"⚠️ Speech gating failed: {e}, using original cues")
            final_cues = raw_cues
            vad_ok = False
        
        # 4. Generate SRT file
        subtitle_path = Path(context.settings['temp_dir']) / context.job_id / "subtitles.srt"
        words_per_caption = int(context.settings.get('words_per_caption', 2))
        
        # Group cues into segments for SRT generation
        segments_for_srt = self._group_cues_into_segments(final_cues, segment_size=10)
        
        self.subtitle_generator.generate_word_by_word_srt(
            segments_for_srt,
            str(subtitle_path),
            words_per_caption=words_per_caption
        )
        
        # 5. Validate SRT file
        if not subtitle_path.exists():
            raise AudioProcessingException(
                f"SRT file not created at {subtitle_path}",
                error_code=ErrorCode.SUBTITLE_GENERATION_FAILED,
                job_id=context.job_id,
            )
        
        srt_size = subtitle_path.stat().st_size
        if srt_size == 0:
            raise AudioProcessingException(
                "SRT file is empty (0 bytes)",
                error_code=ErrorCode.SUBTITLE_GENERATION_FAILED,
                details={'path': str(subtitle_path)},
                job_id=context.job_id,
            )
        
        logger.info(
            f"✅ Subtitles generated: {len(final_cues)} words → {len(segments_for_srt)} segments → "
            f"~{len(final_cues) // words_per_caption} captions, {words_per_caption} words/caption, "
            f"vad_ok={vad_ok}"
        )
        
        # Update context
        context.subtitle_path = subtitle_path
        context.raw_cues = raw_cues
        context.gated_cues = final_cues
        
        return {
            'subtitle_path': str(subtitle_path),
            'raw_cues_count': len(raw_cues),
            'gated_cues_count': len(final_cues),
            'segments_count': len(segments_for_srt),
            'vad_ok': vad_ok,
            'words_per_caption': words_per_caption,
        }
    
    def _extract_word_cues(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract word-level cues from transcription segments with weighted timing."""
        raw_cues = []

        for segment in segments:
            words = segment.get('words', [])

            if words:
                for word_data in words:
                    raw_cues.append({
                        'start': word_data['start'],
                        'end': word_data['end'],
                        'text': word_data['word']
                    })
            else:
                # Fallback: weighted distribution by word length
                text = segment.get('text', '').strip()
                if text:
                    words_list = re.findall(r'\S+', text)
                    seg_start = segment.get('start', 0.0)
                    seg_end = segment.get('end', seg_start + 1.0)
                    seg_duration = seg_end - seg_start

                    if words_list:
                        total_weight = sum(len(w) for w in words_list)
                        if total_weight == 0:
                            total_weight = len(words_list)

                        cursor = seg_start
                        for word in words_list:
                            word_weight = len(word) if len(word) > 0 else 1
                            word_duration = seg_duration * (word_weight / total_weight)
                            raw_cues.append({
                                'start': cursor,
                                'end': cursor + word_duration,
                                'text': word
                            })
                            cursor += word_duration

        return raw_cues

    async def _transcribe_with_retry(self, audio_path: str, language: str) -> list[dict[str, Any]]:
        """Transcribe audio with exponential backoff retry."""
        last_error = None
        for attempt in range(MAX_SUBTITLE_RETRIES):
            try:
                return await self.api_client.transcribe_audio(audio_path, language)
            except Exception as exc:
                last_error = exc
                wait = min(2 ** attempt, MAX_BACKOFF_SECONDS)
                logger.warning(
                    "Transcription attempt %d/%d failed: %s. Retrying in %ds...",
                    attempt + 1, MAX_SUBTITLE_RETRIES, exc, wait,
                )
                await asyncio.sleep(wait)

        raise AudioProcessingException(
            f"Transcription failed after {MAX_SUBTITLE_RETRIES} attempts: {last_error}",
            error_code=ErrorCode.TRANSCRIPTION_FAILED,
            job_id=getattr(self, '_job_id', None),
        )
    
    def _group_cues_into_segments(self, cues: list[dict[str, Any]], segment_size: int = 10) -> list[dict[str, Any]]:
        """Group cues into segments"""
        segments = []
        
        for i in range(0, len(cues), segment_size):
            chunk = cues[i:i+segment_size]
            if chunk:
                segments.append({
                    'start': chunk[0]['start'],
                    'end': chunk[-1]['end'],
                    'text': ' '.join(c['text'] for c in chunk)
                })
        
        return segments
    
    async def compensate(self, context: StageContext) -> None:
        """Delete subtitle file"""
        if context.subtitle_path and context.subtitle_path.exists():
            logger.info(f"↩️  Deleting subtitle file: {context.subtitle_path}")
            context.subtitle_path.unlink()
