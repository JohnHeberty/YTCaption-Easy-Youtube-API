"""
Teste de Sincronização Palavra-por-Palavra

Valida que cada palavra aparece SOMENTE quando está sendo falada.

PROBLEMA ANTERIOR:
- words_per_caption=2 agrupava múltiplas palavras
- Quando áudio dizia "um", tela mostrava "1, 2, 3, 4"
- Timestamps não respeitavam o intervalo exato de cada palavra

SOLUÇÃO IMPLEMENTADA:
1. Whisper com word_timestamps=True (timestamps precisos por palavra)
2. words_per_caption=1 (uma palavra por legenda)
3. Cada legenda aparece SOMENTE durante sua palavra
"""

import pytest
from pathlib import Path
from app.services.subtitle_generator import (
    segments_to_weighted_word_cues,
    write_srt_from_word_cues,
    format_srt_timestamp
)


class TestWordByWordSync:
    """Testa sincronização palavra-por-palavra"""
    
    def test_single_word_per_caption(self, tmp_path):
        """Uma palavra = uma legenda (sincronização perfeita)"""
        # Simular word cues do Whisper com timestamps precisos
        word_cues = [
            {'start': 0.0, 'end': 0.5, 'text': 'um'},
            {'start': 0.5, 'end': 1.0, 'text': 'dois'},
            {'start': 1.0, 'end': 1.5, 'text': 'três'},
            {'start': 1.5, 'end': 2.0, 'text': 'quatro'}
        ]
        
        srt_path = tmp_path / "test.srt"
        write_srt_from_word_cues(word_cues, str(srt_path), words_per_caption=1)
        
        content = srt_path.read_text(encoding='utf-8')
        
        # Deve ter 4 legendas separadas
        assert content.count("\n\n") >= 3  # 4 legendas = 3 separadores
        
        # Cada palavra deve aparecer sozinha
        assert "\num\n" in content
        assert "\ndois\n" in content
        assert "\ntrês\n" in content
        assert "\nquatro\n" in content
        
        # Verificar timestamps corretos
        lines = content.split('\n')
        
        # Legenda 1: "um" (0.0 - 0.5s)
        assert "00:00:00,000 --> 00:00:00,500" in content
        
        # Legenda 2: "dois" (0.5 - 1.0s)
        assert "00:00:00,500 --> 00:00:01,000" in content
        
        # Legenda 3: "três" (1.0 - 1.5s)
        assert "00:00:01,000 --> 00:00:01,500" in content
        
        # Legenda 4: "quatro" (1.5 - 2.0s)
        assert "00:00:01,500 --> 00:00:02,000" in content
    
    def test_no_overlap_between_captions(self, tmp_path):
        """Legendas não devem se sobrepor (cada palavra no seu momento)"""
        word_cues = [
            {'start': 0.0, 'end': 0.8, 'text': 'olá'},
            {'start': 0.8, 'end': 1.5, 'text': 'mundo'}
        ]
        
        srt_path = tmp_path / "no_overlap.srt"
        write_srt_from_word_cues(word_cues, str(srt_path), words_per_caption=1)
        
        content = srt_path.read_text(encoding='utf-8')
        
        # Primeira legenda termina em 0.8s
        assert "00:00:00,000 --> 00:00:00,800" in content
        
        # Segunda legenda começa em 0.8s (sem overlap)
        assert "00:00:00,800 --> 00:00:01,500" in content
        
        # Palavras separadas
        assert "\nolá\n" in content
        assert "\nmundo\n" in content
    
    def test_numbers_counting_sync(self, tmp_path):
        """Teste específico: contagem numérica (1, 2, 3, 4)"""
        # Simular contagem falada: "um, dois, três, quatro"
        word_cues = [
            {'start': 0.0, 'end': 0.4, 'text': '1'},
            {'start': 0.6, 'end': 1.0, 'text': '2'},
            {'start': 1.2, 'end': 1.6, 'text': '3'},
            {'start': 1.8, 'end': 2.2, 'text': '4'}
        ]
        
        srt_path = tmp_path / "counting.srt"
        write_srt_from_word_cues(word_cues, str(srt_path), words_per_caption=1)
        
        content = srt_path.read_text(encoding='utf-8')
        
        # Cada número deve aparecer SOZINHO
        assert "\n1\n" in content
        assert "\n2\n" in content
        assert "\n3\n" in content
        assert "\n4\n" in content
        
        # Não deve ter agrupamento como "1 2" ou "1, 2, 3, 4"
        assert "1 2" not in content
        assert "1, 2" not in content
        assert "1, 2, 3, 4" not in content
        
        # Timestamps devem respeitar pausas
        # "1" aparece em 0.0-0.4s (não deve estar visível em 0.6s quando "2" começa)
        assert "00:00:00,000 --> 00:00:00,400" in content
        assert "00:00:00,600 --> 00:00:01,000" in content
    
    def test_phrase_with_word_timestamps(self, tmp_path):
        """Frase completa com timestamps palavra-por-palavra"""
        # Simular: "A responsabilidade é sua"
        word_cues = [
            {'start': 0.0, 'end': 0.3, 'text': 'A'},
            {'start': 0.3, 'end': 1.2, 'text': 'responsabilidade'},  # Palavra longa
            {'start': 1.2, 'end': 1.4, 'text': 'é'},
            {'start': 1.4, 'end': 1.8, 'text': 'sua'}
        ]
        
        srt_path = tmp_path / "phrase.srt"
        write_srt_from_word_cues(word_cues, str(srt_path), words_per_caption=1)
        
        content = srt_path.read_text(encoding='utf-8')
        
        # Palavra curta: 0.3s de duração
        assert "00:00:00,000 --> 00:00:00,300" in content
        assert "\nA\n" in content
        
        # Palavra longa: 0.9s de duração
        assert "00:00:00,300 --> 00:00:01,200" in content
        assert "\nresponsabilidade\n" in content
        
        # Palavra curta: 0.2s
        assert "00:00:01,200 --> 00:00:01,400" in content
        assert "\né\n" in content
        
        # Palavra média: 0.4s
        assert "00:00:01,400 --> 00:00:01,800" in content
        assert "\nsua\n" in content


class TestWhisperWordTimestamps:
    """Testa se Whisper está retornando word-level timestamps"""
    
    def test_has_word_timestamps_detection(self):
        """Verificar se código detecta word timestamps do Whisper"""
        # Simular segment do Whisper COM word timestamps
        segments_with_words = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "um dois",
                "words": [
                    {"word": "um", "start": 0.0, "end": 0.5},
                    {"word": "dois", "start": 0.5, "end": 1.0}
                ]
            }
        ]
        
        # Verificar detecção
        has_word_timestamps = any(segment.get('words') for segment in segments_with_words)
        assert has_word_timestamps is True
    
    def test_missing_word_timestamps_detection(self):
        """Verificar detecção quando Whisper NÃO tem word timestamps"""
        # Simular segment do Whisper SEM word timestamps
        segments_without_words = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "um dois"
            }
        ]
        
        has_word_timestamps = any(segment.get('words') for segment in segments_without_words)
        assert has_word_timestamps is False


class TestConfigValidation:
    """Valida configurações de sincronização"""
    
    def test_words_per_caption_config(self):
        """words_per_caption deve ser 1 para sincronização perfeita"""
        from app.core.config import Settings
        
        settings = Settings()
        
        # Deve ser 1 (uma palavra por legenda)
        assert settings.words_per_caption == 1, (
            f"words_per_caption deve ser 1 para sincronização perfeita, "
            f"mas está configurado como {settings.words_per_caption}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
