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
        
        audio_bytes, duration = await client.clone_voice(
            text="Esta voz foi clonada usando XTTS",
            reference_audio=ref_audio,
            language="pt"
        )
        
        assert len(audio_bytes) > 0, "Áudio clonado vazio"
        assert duration > 0, "Duração inválida"
    
    @pytest.mark.asyncio
    async def test_clone_voice_multiple_references(self):
        """Testa clonagem com múltiplos áudios de referência"""
        client = XTTSClient(device='cpu')
        
        # Lista de referências (pode ter 1-3 samples)
        ref_audios = [
            "/app/uploads/clone_20251126031159965237.ogg",
        ]
        
        # Filtra apenas arquivos que existem
        existing_refs = [f for f in ref_audios if os.path.exists(f)]
        
        if len(existing_refs) == 0:
            pytest.skip("Nenhum áudio de referência encontrado")
        
        audio_bytes, duration = await client.clone_voice(
            text="Clonagem com múltiplas referências",
            reference_audio=existing_refs,
            language="pt"
        )
        
        assert len(audio_bytes) > 0, "Áudio vazio"
        assert duration > 0, "Duração inválida"
    
    @pytest.mark.asyncio
    async def test_clone_voice_with_text_reference(self):
        """Testa clonagem com texto de referência (condicionamento)"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        audio_bytes, duration = await client.clone_voice(
            text="Este é o texto a ser sintetizado",
            reference_audio=ref_audio,
            reference_text="Texto original do áudio de referência",
            language="pt"
        )
        
        assert len(audio_bytes) > 0, "Áudio vazio"
        assert duration > 0, "Duração inválida"
    
    @pytest.mark.asyncio
    async def test_clone_voice_invalid_reference(self):
        """Testa que áudio de referência inexistente retorna erro"""
        client = XTTSClient(device='cpu')
        
        with pytest.raises(FileNotFoundError, match="reference|referência|not found"):
            await client.clone_voice(
                text="Teste",
                reference_audio="/caminho/inexistente.wav",
                language="pt"
            )
    
    @pytest.mark.asyncio
    async def test_clone_voice_quality_settings(self):
        """Testa configurações de qualidade de clonagem"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        # Gera áudio com qualidade alta
        audio_high, duration_high = await client.clone_voice(
            text="Teste de qualidade alta",
            reference_audio=ref_audio,
            language="pt",
            temperature=0.7,  # Mais determinístico
            repetition_penalty=5.0  # Menos repetição
        )
        
        assert len(audio_high) > 0, "Áudio qualidade alta vazio"
        
        # Gera áudio com qualidade baixa (mais rápido)
        audio_low, duration_low = await client.clone_voice(
            text="Teste de qualidade baixa",
            reference_audio=ref_audio,
            language="pt",
            temperature=1.0,  # Mais variação
            repetition_penalty=2.0
        )
        
        assert len(audio_low) > 0, "Áudio qualidade baixa vazio"
        
        # Qualidade alta deve ser mais consistente (não necessariamente maior)
        # Mas ambos devem ter duração similar para mesmo texto
        assert abs(duration_high - duration_low) < 2, "Durações muito diferentes"
