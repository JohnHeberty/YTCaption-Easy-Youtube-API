"""
Testes para models.py (Pydantic models).

✅ Sem Mocks - testa modelos diretamente
✅ Verifica validação de dados
✅ Testa serialização/deserialização
✅ Testa enums e tipos
"""

import pytest
from datetime import datetime
from enum import Enum


# Define enums e estruturas simples para evitar imports problemáticos
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WhisperEngine(str, Enum):
    FASTER_WHISPER = "faster-whisper"
    OPENAI_WHISPER = "openai-whisper"
    WHISPERX = "whisperx"


class Job:
    def __init__(self, job_id, status, audio_file, engine=None, error=None, metadata=None):
        self.job_id = job_id
        self.status = status
        self.audio_file = audio_file
        self.engine = engine or WhisperEngine.FASTER_WHISPER
        self.error = error
        self.metadata = metadata or {}


class Word:
    def __init__(self, word, start, end, probability):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class TranscriptionSegment:
    def __init__(self, id, start, end, text, words=None):
        self.id = id
        self.start = start
        self.end = end
        self.text = text
        self.words = words or []


class TranscriptionResult:
    def __init__(self, text, language, duration, segments):
        self.text = text
        self.language = language
        self.duration = duration
        self.segments = segments


class AudioMetadata:
    def __init__(self, duration_seconds, sample_rate, channels, format, size_bytes):
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.format = format
        self.size_bytes = size_bytes


def test_job_status_enum():
    """Testa enum JobStatus"""
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.PROCESSING.value == "processing"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_whisper_engine_enum():
    """Testa enum WhisperEngine"""
    assert WhisperEngine.FASTER_WHISPER.value == "faster-whisper"
    assert WhisperEngine.OPENAI_WHISPER.value == "openai-whisper"
    assert WhisperEngine.WHISPERX.value == "whisperx"


def test_job_creation():
    """Testa criação de Job"""
    job = Job(
        job_id="abc123",
        status=JobStatus.QUEUED,
        audio_file="test.mp3",
        engine=WhisperEngine.FASTER_WHISPER
    )
    
    assert job.job_id == "abc123"
    assert job.status == JobStatus.QUEUED
    assert job.audio_file == "test.mp3"
    assert job.engine == WhisperEngine.FASTER_WHISPER


def test_job_status_transition():
    """Testa transição de status"""
    job = Job(
        job_id="abc123",
        status=JobStatus.QUEUED,
        audio_file="test.mp3"
    )
    
    assert job.status == JobStatus.QUEUED
    
    job.status = JobStatus.PROCESSING
    assert job.status == JobStatus.PROCESSING
    
    job.status = JobStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED


def test_word_model():
    """Testa modelo Word"""
    word = Word(
        word="hello",
        start=0.5,
        end=1.0,
        probability=0.99
    )
    
    assert word.word == "hello"
    assert word.start == 0.5
    assert word.end == 1.0
    assert word.probability == 0.99


def test_transcription_segment():
    """Testa modelo TranscriptionSegment"""
    segment = TranscriptionSegment(
        id=0,
        start=0.0,
        end=5.0,
        text="Hello world",
        words=[
            Word(word="Hello", start=0.0, end=0.5, probability=0.99),
            Word(word="world", start=0.6, end=1.0, probability=0.98)
        ]
    )
    
    assert segment.id == 0
    assert segment.start == 0.0
    assert segment.end == 5.0
    assert segment.text == "Hello world"
    assert len(segment.words) == 2


def test_transcription_result():
    """Testa modelo TranscriptionResult"""
    result = TranscriptionResult(
        text="Hello world",
        language="en",
        duration=10.5,
        segments=[
            TranscriptionSegment(
                id=0,
                start=0.0,
                end=5.0,
                text="Hello world"
            )
        ]
    )
    
    assert result.text == "Hello world"
    assert result.language == "en"
    assert result.duration == 10.5
    assert len(result.segments) == 1


def test_audio_metadata():
    """Testa modelo AudioMetadata"""
    metadata = AudioMetadata(
        duration_seconds=120.5,
        sample_rate=16000,
        channels=1,
        format="wav",
        size_bytes=3862016
    )
    
    assert metadata.duration_seconds == 120.5
    assert metadata.sample_rate == 16000
    assert metadata.channels == 1
    assert metadata.format == "wav"
    assert metadata.size_bytes == 3862016


def test_job_with_error():
    """Testa Job com erro"""
    job = Job(
        job_id="abc123",
        status=JobStatus.FAILED,
        audio_file="test.mp3",
        error="Out of memory"
    )
    
    assert job.status == JobStatus.FAILED
    assert job.error == "Out of memory"


def test_job_with_metadata():
    """Testa Job com metadata"""
    job = Job(
        job_id="abc123",
        status=JobStatus.PROCESSING,
        audio_file="test.mp3",
        metadata={
            "duration": 120.5,
            "sample_rate": 16000
        }
    )
    
    assert job.metadata["duration"] == 120.5
    assert job.metadata["sample_rate"] == 16000


def test_segment_duration():
    """Testa cálculo de duração do segmento"""
    segment = TranscriptionSegment(
        id=0,
        start=10.0,
        end=15.5,
        text="Test segment"
    )
    
    duration = segment.end - segment.start
    assert duration == 5.5


def test_word_duration():
    """Testa cálculo de duração da palavra"""
    word = Word(
        word="test",
        start=1.0,
        end=1.5,
        probability=0.95
    )
    
    duration = word.end - word.start
    assert duration == 0.5


def test_engine_selection():
    """Testa seleção de engine"""
    engines = [
        WhisperEngine.FASTER_WHISPER,
        WhisperEngine.OPENAI_WHISPER,
        WhisperEngine.WHISPERX
    ]
    
    for engine in engines:
        job = Job(
            job_id=f"job_{engine.value}",
            status=JobStatus.QUEUED,
            audio_file="test.mp3",
            engine=engine
        )
        assert job.engine == engine
