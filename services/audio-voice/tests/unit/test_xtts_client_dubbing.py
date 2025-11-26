"""
Testes unitários XTTSClient - Dubbing
Sprint 1.2 (RED PHASE): Testes vão FALHAR até implementar
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.xtts_client import XTTSClient
from app.models import VoiceProfile


class TestXTTSClientDubbing:
    """Testes de geração de dubbing (síntese de fala)"""
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_basic(self):
        """Testa geração de dubbing básico sem clonagem"""
        client = XTTSClient(device='cpu')
        
        audio_bytes, duration = await client.generate_dubbing(
            text="Olá, mundo!",
            language="pt",
            voice_preset="female_generic"
        )
        
        assert len(audio_bytes) > 0, "Áudio vazio!"
        assert duration > 0, "Duração inválida!"
        assert duration < 10, "Duração muito longa para texto curto"
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_with_profile(self):
        """Testa dubbing com VoiceProfile (voice cloning)"""
        client = XTTSClient(device='cpu')
        
        # Mock de VoiceProfile
        profile = VoiceProfile(
            id="test_voice_123",
            name="Test Voice",
            language="pt",
            reference_audio_path="/app/uploads/clone_20251126031159965237.ogg",
            reference_text="Texto de referência para clonagem",
            profile_path="voice_profiles/test_voice_123"
        )
        
        audio_bytes, duration = await client.generate_dubbing(
            text="Teste com perfil clonado",
            language="pt",
            voice_profile=profile
        )
        
        assert len(audio_bytes) > 0, "Áudio com clonagem vazio"
        assert duration > 0, "Duração inválida"
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_long_text(self):
        """Testa dubbing com texto longo (>400 tokens)"""
        client = XTTSClient(device='cpu')
        
        # Texto longo: ~150 palavras
        long_text = "Este é um texto muito longo para testar a capacidade do XTTS de processar textos extensos. " * 20
        
        audio_bytes, duration = await client.generate_dubbing(
            text=long_text,
            language="pt",
            voice_preset="male_generic"
        )
        
        assert len(audio_bytes) > 0, "Áudio longo vazio"
        assert duration > 10, "Duração muito curta para texto longo"
        assert duration < 300, "Duração excessiva (timeout?)"
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_empty_text(self):
        """Testa que texto vazio retorna erro"""
        client = XTTSClient(device='cpu')
        
        with pytest.raises(ValueError, match="texto vazio|empty text"):
            await client.generate_dubbing(
                text="",
                language="pt",
                voice_preset="female_generic"
            )
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_invalid_language(self):
        """Testa que linguagem inválida retorna erro"""
        client = XTTSClient(device='cpu')
        
        with pytest.raises(ValueError, match="linguagem|language|suportada"):
            await client.generate_dubbing(
                text="Test",
                language="xyz",  # Linguagem inválida
                voice_preset="female_generic"
            )
    
    @pytest.mark.asyncio
    async def test_generate_dubbing_output_format(self):
        """Testa formato do áudio retornado"""
        client = XTTSClient(device='cpu')
        
        audio_bytes, duration = await client.generate_dubbing(
            text="Teste de formato",
            language="pt",
            voice_preset="female_generic"
        )
        
        # Valida se é WAV (header: 'RIFF')
        assert audio_bytes[:4] == b'RIFF', "Não é formato WAV válido"
        assert b'WAVE' in audio_bytes[:20], "Header WAV inválido"
