"""
Domain layer - Enterprise patterns for job processing

🎯 Domain-Driven Design:
    - JobStage: Template Method pattern for processing stages
    - JobProcessor: Chain of Responsibility pattern
    - StageContext: Rich domain context for stages
    - Saga compensation for rollback

📦 Exports:
    - JobStage, StageContext, StageResult
    - JobProcessor
    - All concrete stage classes
"""

from .job_stage import JobStage, StageContext, StageResult, StageStatus
from .job_processor import JobProcessor

# Concrete stages
from .stages.analyze_audio_stage import AnalyzeAudioStage
from .stages.fetch_shorts_stage import FetchShortsStage
from .stages.download_shorts_stage import DownloadShortsStage
from .stages.select_shorts_stage import SelectShortsStage
from .stages.assemble_video_stage import AssembleVideoStage
from .stages.generate_subtitles_stage import GenerateSubtitlesStage
from .stages.final_composition_stage import FinalCompositionStage
from .stages.trim_video_stage import TrimVideoStage

__all__ = [
    # Base classes
    'JobStage',
    'StageContext',
    'StageResult',
    'StageStatus',
    'JobProcessor',
    
    # Concrete stages
    'AnalyzeAudioStage',
    'FetchShortsStage',
    'DownloadShortsStage',
    'SelectShortsStage',
    'AssembleVideoStage',
    'GenerateSubtitlesStage',
    'FinalCompositionStage',
    'TrimVideoStage',
]
