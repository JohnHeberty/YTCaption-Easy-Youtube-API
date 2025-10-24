"""Domain entities package.

This module re-exports entity classes. Previously TranscriptionSegment
was defined as a value object under `src.domain.value_objects`. Some
modules import `TranscriptionSegment` from `src.domain.entities` so
we re-export it here for backward compatibility.
"""
from src.domain.entities.transcription import Transcription
from src.domain.entities.video_file import VideoFile
from src.domain.value_objects import TranscriptionSegment

__all__ = ["Transcription", "VideoFile", "TranscriptionSegment"]
