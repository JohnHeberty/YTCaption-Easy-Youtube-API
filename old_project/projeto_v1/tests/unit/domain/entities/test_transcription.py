"""
Testes unitários para a entidade Transcription.
"""
import pytest
from datetime import datetime
from pathlib import Path
from src.domain.entities.transcription import Transcription
from src.domain.value_objects.transcription_segment import TranscriptionSegment
from src.domain.value_objects.youtube_url import YouTubeURL


class TestTranscription:
    """Testes para a entidade Transcription."""
    
    def test_create_transcription_with_default_values(self):
        """Deve criar transcription com valores padrão."""
        transcription = Transcription()
        
        assert transcription.id is not None
        assert isinstance(transcription.id, str)
        assert transcription.youtube_url is None
        assert transcription.segments == []
        assert transcription.language is None
        assert isinstance(transcription.created_at, datetime)
        assert transcription.processing_time is None
    
    def test_create_transcription_with_youtube_url(self):
        """Deve criar transcription com URL do YouTube."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=test123")
        
        transcription = Transcription(
            youtube_url=url,
            language="en"
        )
        
        assert transcription.youtube_url == url
        assert transcription.language == "en"
    
    def test_add_segment(self):
        """Deve adicionar segmento à transcription."""
        transcription = Transcription()
        
        segment = TranscriptionSegment(
            text="Hello world",
            start=0.0,
            end=3.0
        )
        
        transcription.add_segment(segment)
        
        assert len(transcription.segments) == 1
        assert transcription.segments[0].text == "Hello world"
    
    def test_get_full_text(self):
        """Deve retornar texto completo da transcrição."""
        transcription = Transcription()
        
        transcription.add_segment(TranscriptionSegment(text="First", start=0.0, end=1.0))
        transcription.add_segment(TranscriptionSegment(text="Second", start=1.0, end=2.0))
        transcription.add_segment(TranscriptionSegment(text="Third", start=2.0, end=3.0))
        
        full_text = transcription.get_full_text()
        
        assert full_text == "First Second Third"
    
    def test_duration_property(self):
        """Deve calcular duração total da transcrição."""
        transcription = Transcription()
        
        transcription.add_segment(TranscriptionSegment(text="Test 1", start=0.0, end=5.5))
        transcription.add_segment(TranscriptionSegment(text="Test 2", start=5.5, end=10.0))
        
        assert transcription.duration == 10.0
    
    def test_duration_empty_transcription(self):
        """Duração de transcrição vazia deve ser 0."""
        transcription = Transcription()
        
        assert transcription.duration == 0.0
    
    def test_is_complete_property(self):
        """Deve verificar se transcrição está completa."""
        transcription = Transcription()
        
        # Não completa: sem segmentos e sem language
        assert not transcription.is_complete
        
        # Não completa: tem segmentos mas sem language
        transcription.add_segment(TranscriptionSegment(text="Test", start=0.0, end=1.0))
        assert not transcription.is_complete
        
        # Completa: tem segmentos e language
        transcription.language = "en"
        assert transcription.is_complete
    
    def test_to_dict(self):
        """Deve converter transcrição para dict."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=abc123")
        transcription = Transcription(
            youtube_url=url,
            language="pt"
        )
        transcription.add_segment(TranscriptionSegment(text="Teste", start=0.0, end=2.5))
        
        data = transcription.to_dict()
        
        assert data["video_id"] == "abc123"
        assert data["language"] == "pt"
        assert data["full_text"] == "Teste"
        assert data["total_segments"] == 1
        assert "created_at" in data
    
    def test_to_srt(self):
        """Deve converter para formato SRT."""
        transcription = Transcription()
        transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.0))
        
        srt_content = transcription.to_srt()
        
        assert isinstance(srt_content, str)
        # SRT deve ter conteúdo
        assert len(srt_content) > 0
    
    def test_to_vtt(self):
        """Deve converter para formato WebVTT."""
        transcription = Transcription()
        transcription.add_segment(TranscriptionSegment(text="Hello", start=0.0, end=2.0))
        
        vtt_content = transcription.to_vtt()
        
        assert isinstance(vtt_content, str)
        assert vtt_content.startswith("WEBVTT")
