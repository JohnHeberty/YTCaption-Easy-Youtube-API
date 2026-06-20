"""Conversor de legendas — formatos SRT, VTT, TXT, LRC e SAM.

Responsabilidade única: transformar segmentos do Whisper (list[dict]) em 
strings formatadas para cada tipo de legenda suportado pelo sistema.

Classe pura sem dependências externas ou estado mutável.
"""
from __future__ import annotations

from typing import Any


class CaptionFormatter:
    """Formata segmentos de transcrição para múltiplos formatos de legenda."""

    @staticmethod
    def to_srt(segments: list[dict[str, Any]]) -> str:
        srt_content = ""
        
        for i, segment in enumerate(segments, 1):
            start_time = CaptionFormatter._seconds_to_timestamp(segment["start"], "srt")
            end_time = CaptionFormatter._seconds_to_timestamp(segment["end"], "srt")
            text = segment["text"].strip()
            
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        
        return srt_content

    @staticmethod
    def to_vtt(segments: list[dict[str, Any]]) -> str:
        vtt_lines = ["WEBVTT", ""]
        
        for i, segment in enumerate(segments, 1):
            start_time = CaptionFormatter._seconds_to_timestamp(segment["start"], "vtt")
            end_time = CaptionFormatter._seconds_to_timestamp(segment["end"], "vtt")
            text = segment["text"].strip()
            
            vtt_lines.append(f"{i}")
            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(text)
            vtt_lines.append("")

        return "\n".join(vtt_lines)

    @staticmethod
    def to_txt(segments: list[dict[str, Any]]) -> str:
        texts = []
        
        for segment in segments:
            text = segment["text"].strip()
            if text:
                texts.append(text)

        return " ".join(texts)

    @staticmethod
    def to_lrc(segments: list[dict[str, Any]]) -> str:
        lrc_lines = []
        
        for segment in segments:
            timestamp = CaptionFormatter._seconds_to_timestamp(segment["start"], "lrc")
            text = segment["text"].strip()
            
            if text:
                lrc_lines.append(f"[{timestamp}]{text}")

        return "\n".join(lrc_lines)

    @staticmethod
    def to_sam(segments: list[dict[str, Any]]) -> str:
        sam_content = ""
        
        for i, segment in enumerate(segments, 1):
            start_time = CaptionFormatter._seconds_to_timestamp(segment["start"], "srt")
            end_time = CaptionFormatter._seconds_to_timestamp(segment["end"], "srt")
            text = segment["text"].strip()

            sam_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"

        return sam_content

    @staticmethod
    def _seconds_to_timestamp(seconds: float, fmt: str = "srt") -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        if fmt == "vtt":
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
        
        elif fmt == "lrc":
            return f"{minutes:02d}:{secs:02d}.{millis // 10:02d}"

        else:
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @classmethod
    def format(cls, segments: list[dict[str, Any]], output_format: str = "srt") -> str:
        formatters = {
            "srt": cls.to_srt,
            "vtt": cls.to_vtt,
            "txt": cls.to_txt,
            "lrc": cls.to_lrc,
            "sam": cls.to_sam,
        }

        formatter_fn = formatters.get(output_format.lower(), cls.to_srt)
        return formatter_fn(segments)


# Aliases para compatibilidade com código legado que usa nomes de método privados.
def convert_to_srt(segments: list[dict[str, Any]]) -> str:
    """Alias legacy — use CaptionFormatter.format() ou .to_srt()."""
    return CaptionFormatter.to_srt(segments)

def seconds_to_srt_time(seconds: float) -> str:
    """Alias legacy — use CaptionFormatter._seconds_to_timestamp()."""
    return CaptionFormatter._seconds_to_timestamp(seconds, "srt")
