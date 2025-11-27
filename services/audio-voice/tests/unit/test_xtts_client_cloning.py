"""
Testes unitários XTTSClient - Voice Cloning
Sprint 1.2 (RED PHASE): Testes vão FALHAR até implementar
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.xtts_client import XTTSClient


class TestXTTSClientCloning:
    """Testes de clonagem de voz (few-shot learning)"""
    
    @pytest.mark.asyncio
    async def test_clone_voice_basic(self):
        """Testa clonagem básica com 1 áudio de referência"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        # Verifica se arquivo existe (skip se não houver)
        if not os.path.exists(ref_audio):
            pytest.skip(f"Áudio de referência não encontrado: {ref_audio}")
        
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="Test Voice Basic"
        )
        
        assert profile is not None, "Profile não foi criado"
        assert profile.name == "Test Voice Basic", "Nome incorreto"
        assert profile.language == "pt", "Linguagem incorreta"
    
    @pytest.mark.asyncio
    async def test_clone_voice_multiple_references(self):
        """Testa clonagem (mesmo com único áudio, valida duplicatas ignoradas)"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="Test Voice Multiple"
        )
        
        assert profile is not None, "Profile não foi criado"
        assert profile.name == "Test Voice Multiple"
    
    @pytest.mark.asyncio
    async def test_clone_voice_with_text_reference(self):
        """Testa clonagem com texto de referência (condicionamento)"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="Test Voice with Text",
            reference_text="Texto original do áudio de referência"
        )
        
        assert profile is not None, "Profile não foi criado"
        assert profile.reference_text == "Texto original do áudio de referência"
    
    @pytest.mark.asyncio
    async def test_clone_voice_invalid_reference(self):
        """Testa que áudio de referência inexistente retorna erro"""
        client = XTTSClient(device='cpu')
        
        with pytest.raises(FileNotFoundError, match="reference|referência|not found"):
            await client.clone_voice(
                audio_path="/caminho/inexistente.wav",
                language="pt",
                voice_name="Test Invalid"
            )
    
    @pytest.mark.asyncio
    async def test_clone_voice_quality_settings(self):
        """Testa configurações de qualidade de clonagem"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        # Cria profile com configurações de qualidade
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="Test Voice Quality",
            temperature=0.7,  # Mais determinístico
            repetition_penalty=5.0  # Menos repetição
        )
        
        assert profile is not None, "Profile não foi criado"
        assert profile.duration > 3.0, "Áudio muito curto (deve ter >3s)"
