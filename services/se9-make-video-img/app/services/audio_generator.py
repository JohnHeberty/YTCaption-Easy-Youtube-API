"""Audio generation service using SE7."""
import os
from common.log_utils import get_logger
import re
from typing import Optional

from app.core.constants import CHATTERBOX_MAX_CHARS
from app.core.models import NarrationSegment
from app.infrastructure.http_client import SE7Client

logger = get_logger(__name__)


class AudioGenerator:
    """Generate audio from narration segments using SE7."""

    def __init__(self):
        self.client = SE7Client()

    async def close(self):
        await self.client.close()

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks respecting Chatterbox limits."""
        if len(text) <= CHATTERBOX_MAX_CHARS:
            return [text]

        chunks = []
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= CHATTERBOX_MAX_CHARS:
                current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(para) <= CHATTERBOX_MAX_CHARS:
                    current_chunk = para
                else:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    if len(sentences) <= 1:
                        for i in range(0, len(para), CHATTERBOX_MAX_CHARS):
                            chunks.append(para[i:i + CHATTERBOX_MAX_CHARS])
                        current_chunk = ""
                    else:
                        current_chunk = ""
                        for sent in sentences:
                            if len(current_chunk) + len(sent) + 1 <= CHATTERBOX_MAX_CHARS:
                                current_chunk = f"{current_chunk} {sent}".strip() if current_chunk else sent
                            else:
                                if current_chunk:
                                    chunks.append(current_chunk)
                                current_chunk = sent[:CHATTERBOX_MAX_CHARS]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _concatenate_narration(self, segments: list[NarrationSegment]) -> str:
        """Concatenate narration segments into a single text."""
        sorted_segs = sorted(segments, key=lambda s: s.t)
        return " ".join(s.text for s in sorted_segs)

    async def generate(
        self,
        narration: list[NarrationSegment],
        voice_id: str = "builtin_feminino",
        output_dir: str = "/tmp",
        normalize_text: bool = True,
    ) -> tuple[str, float]:
        """Generate audio from narration. Returns (audio_path, duration_seconds)."""
        full_text = self._concatenate_narration(narration)
        chunks = self._chunk_text(full_text)

        logger.info(f"Audio generation: {len(chunks)} chunk(s), {len(full_text)} chars total")

        if len(chunks) == 1:
            audio_bytes = await self._generate_single(chunks[0], voice_id, normalize_text)
            audio_path = os.path.join(output_dir, "audio.wav")
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
        else:
            chunk_paths = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Generating chunk {i + 1}/{len(chunks)}")
                audio_bytes = await self._generate_single(chunk, voice_id, normalize_text)
                chunk_path = os.path.join(output_dir, f"audio_chunk_{i}.wav")
                with open(chunk_path, "wb") as f:
                    f.write(audio_bytes)
                chunk_paths.append(chunk_path)

            audio_path = os.path.join(output_dir, "audio.wav")
            await self._concat_wav_files(chunk_paths, audio_path)

            for p in chunk_paths:
                if os.path.exists(p):
                    os.remove(p)

        from app.infrastructure.ffmpeg_utils import get_audio_duration
        duration = await get_audio_duration(audio_path)
        logger.info(f"Audio generated: {audio_path} ({duration:.1f}s)")
        return audio_path, duration

    async def _generate_single(self, text: str, voice_id: str, normalize_text: bool = True) -> bytes:
        """Generate audio for a single text chunk."""
        job_id = await self.client.create_job(text=text, voice_id=voice_id, normalize_text=normalize_text)
        await self.client.poll_job(job_id)
        return await self.client.download_audio(job_id)

    async def _concat_wav_files(self, input_paths: list[str], output_path: str) -> None:
        """Concatenate WAV files using ffmpeg."""
        import asyncio
        args = ["ffmpeg", "-y"]
        for p in input_paths:
            args.extend(["-i", p])

        filter_parts = []
        for i in range(len(input_paths)):
            filter_parts.append(f"[{i}:a]")
        filter_str = f"{''.join(filter_parts)}concat=n={len(input_paths)}:v=0:a=1[out]"

        args.extend([
            "-filter_complex", filter_str,
            "-map", "[out]",
            output_path,
        ])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"WAV concat failed: {stderr.decode(errors='replace')}")
