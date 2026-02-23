"""
Testes Unitários: Melhorias de Sincronização Áudio-Legenda

Testa as novas funções implementadas:
- segments_to_weighted_word_cues() - Timestamps ponderados
- write_srt_from_word_cues() - Escrita SRT direta
- SpeechGatedSubtitles com word_post_pad - Gating melhorado
"""

import pytest
import tempfile
import os
from pathlib import Path

from app.services.subtitle_generator import (
    segments_to_weighted_word_cues,
    write_srt_from_word_cues,
    format_srt_timestamp
)
from app.services.subtitle_postprocessor import SpeechGatedSubtitles, SubtitleCue, SpeechSegment


class TestWeightedTimestamps:
    """Testa timestamps ponderados por comprimento de palavra"""
    
    def test_basic_weighting(self):
        """Palavras curtas devem ter menos tempo que palavras longas"""
        segments = [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "a responsabilidade"
            }
        ]
        
        word_cues = segments_to_weighted_word_cues(segments)
        
        # Verificar que temos 2 palavras
        assert len(word_cues) == 2
        
        # Calcular durações
        word1_duration = word_cues[0]['end'] - word_cues[0]['start']
        word2_duration = word_cues[1]['end'] - word_cues[1]['start']
        
        # Palavra curta "a" (1 char) deve ter menos tempo que "responsabilidade" (17 chars)
        assert word1_duration < word2_duration
        
        # Verificar timestamps
        assert word_cues[0]['start'] == 0.0
        assert word_cues[1]['end'] == 3.0  # Última palavra deve fechar no end do segment
        assert word_cues[0]['text'] == 'a'
        assert word_cues[1]['text'] == 'responsabilidade'
    
    def test_equal_words(self):
        """Palavras de tamanho igual devem ter tempo similar"""
        segments = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "casa mesa"
            }
        ]
        
        word_cues = segments_to_weighted_word_cues(segments)
        
        assert len(word_cues) == 2
        
        duration1 = word_cues[0]['end'] - word_cues[0]['start']
        duration2 = word_cues[1]['end'] - word_cues[1]['start']
        
        # Durações devem ser próximas (ambas têm 4 caracteres)
        assert abs(duration1 - duration2) < 0.1
    
    def test_empty_segment(self):
        """Segments vazios devem ser ignorados"""
        segments = [
            {"start": 0.0, "end": 1.0, "text": ""},
            {"start": 1.0, "end": 2.0, "text": "palavra"}
        ]
        
        word_cues = segments_to_weighted_word_cues(segments)
        
        # Apenas a palavra válida
        assert len(word_cues) == 1
        assert word_cues[0]['text'] == 'palavra'
    
    def test_multiple_segments(self):
        """Processar múltiplos segments corretamente"""
        segments = [
            {"start": 0.0, "end": 1.0, "text": "primeiro"},
            {"start": 1.0, "end": 2.0, "text": "segundo terceiro"}
        ]
        
        word_cues = segments_to_weighted_word_cues(segments)
        
        assert len(word_cues) == 3
        assert word_cues[0]['text'] == 'primeiro'
        assert word_cues[1]['text'] == 'segundo'
        assert word_cues[2]['text'] == 'terceiro'
        
        # Verificar continuidade
        assert word_cues[0]['start'] == 0.0
        assert word_cues[2]['end'] == 2.0


class TestSRTDirectWrite:
    """Testa escrita SRT direta preservando timestamps"""
    
    def test_basic_srt_generation(self):
        """Gerar SRT básico com 2 palavras por legenda"""
        word_cues = [
            {'start': 0.5, 'end': 1.2, 'text': 'Olá,'},
            {'start': 1.2, 'end': 2.0, 'text': 'como'},
            {'start': 2.0, 'end': 3.2, 'text': 'vai?'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            srt_path = f.name
        
        try:
            write_srt_from_word_cues(word_cues, srt_path, words_per_caption=2)
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar formato SRT
            assert "1\n" in content  # Índice da legenda
            assert "00:00:00,500 --> 00:00:02,000" in content  # Timestamp preservado
            assert "Olá, como" in content  # Texto agrupado
            
            assert "2\n" in content
            assert "00:00:02,000 --> 00:00:03,200" in content
            assert "vai?" in content
        
        finally:
            if os.path.exists(srt_path):
                os.remove(srt_path)
    
    def test_timestamp_preservation(self):
        """Timestamps devem ser preservados exatamente"""
        word_cues = [
            {'start': 0.123, 'end': 0.456, 'text': 'test'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            srt_path = f.name
        
        try:
            write_srt_from_word_cues(word_cues, srt_path, words_per_caption=1)
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verificar precisão dos timestamps (milissegundos)
            assert "00:00:00,123 --> 00:00:00,456" in content
        
        finally:
            if os.path.exists(srt_path):
                os.remove(srt_path)
    
    def test_empty_cues(self):
        """Cues vazios devem ser ignorados"""
        word_cues = [
            {'start': 0.0, 'end': 1.0, 'text': ''},
            {'start': 1.0, 'end': 2.0, 'text': 'palavra'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            srt_path = f.name
        
        try:
            write_srt_from_word_cues(word_cues, srt_path, words_per_caption=1)
            
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Deve ter apenas 1 legenda (a válida)
            assert "1\n" in content  # Legenda #1
            assert "-->" in content  # Timestamp
            assert "palavra" in content
        
        finally:
            if os.path.exists(srt_path):
                os.remove(srt_path)


class TestFormatSRTTimestamp:
    """Testa formatação de timestamps SRT"""
    
    def test_zero_seconds(self):
        assert format_srt_timestamp(0.0) == "00:00:00,000"
    
    def test_subsecond(self):
        assert format_srt_timestamp(0.5) == "00:00:00,500"
    
    def test_seconds(self):
        assert format_srt_timestamp(5.123) == "00:00:05,123"
    
    def test_minutes(self):
        assert format_srt_timestamp(125.456) == "00:02:05,456"
    
    def test_hours(self):
        assert format_srt_timestamp(3661.789) == "01:01:01,789"
    
    def test_negative_becomes_zero(self):
        assert format_srt_timestamp(-1.0) == "00:00:00,000"


class TestImprovedGating:
    """Testa gating melhorado com word_post_pad"""
    
    def test_word_post_pad_parameter(self):
        """Verificar que word_post_pad está disponível"""
        processor = SpeechGatedSubtitles(word_post_pad=0.05)
        assert processor.word_post_pad == 0.05
    
    def test_cue_end_respected(self):
        """Gating deve respeitar cue.end original"""
        processor = SpeechGatedSubtitles(
            pre_pad=0.06,
            post_pad=0.12,
            word_post_pad=0.03
        )
        
        # Cue curto dentro de speech segment longo
        cues = [
            SubtitleCue(0, start=1.0, end=1.5, text="palavra")
        ]
        
        speech_segments = [
            SpeechSegment(start=0.5, end=10.0, confidence=1.0)
        ]
        
        gated = processor.gate_subtitles(cues, speech_segments, audio_duration=15.0)
        
        assert len(gated) == 1
        
        # End deve ser próximo de 1.5 + word_post_pad, NÃO 10.0 + post_pad
        assert gated[0].end < 2.0  # Muito menor que 10.12
        assert gated[0].end >= 1.5  # Pelo menos o original


class TestExceptionHandling:
    """Testa que exceptions têm atributos corretos"""
    
    def test_subtitle_generation_exception(self):
        """SubtitleGenerationException deve ter error_code, não code"""
        from app.shared.exceptions_v2 import SubtitleGenerationException
        
        exc = SubtitleGenerationException(
            reason="Test reason",
            subtitle_path="/tmp/test.srt"
        )
        
        # Deve ter error_code
        assert hasattr(exc, 'error_code')
        assert hasattr(exc, 'message')
        assert hasattr(exc, 'details')
        
        # NÃO deve ter 'code'
        assert not hasattr(exc, 'code')


# Marks para categorizar testes
pytestmark = [
    pytest.mark.unit,
    pytest.mark.subtitle_sync
]
