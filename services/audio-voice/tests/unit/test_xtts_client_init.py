"""
Testes unitários XTTSClient - Instanciação
Sprint 1.2 (RED PHASE): Estes testes vão FALHAR até implementar XTTSClient
"""
import pytest
import sys
import os

# Adiciona app/ ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.xtts_client import XTTSClient  # Import vai falhar inicialmente!


class TestXTTSClientInit:
    """Testes de instanciação do XTTSClient"""
    
    def test_xtts_client_instantiation_cpu(self):
        """Testa se XTTSClient instancia corretamente em CPU"""
        client = XTTSClient(device='cpu')
        
        assert client is not None, "Cliente não foi criado"
        assert client.device == 'cpu', "Device incorreto"
        assert hasattr(client, 'tts'), "Falta atributo tts"
        assert hasattr(client, 'generate_dubbing'), "Falta método generate_dubbing"
        assert hasattr(client, 'clone_voice'), "Falta método clone_voice"
    
    def test_xtts_client_auto_device(self):
        """Testa detecção automática de device (CPU/CUDA)"""
        client = XTTSClient()  # device=None - deve detectar automaticamente
        
        assert client.device in ['cpu', 'cuda'], f"Device inválido: {client.device}"
    
    def test_xtts_client_cuda_if_available(self):
        """Testa uso de CUDA quando disponível"""
        import torch
        
        if torch.cuda.is_available():
            client = XTTSClient(device='cuda')
            assert client.device == 'cuda', "Deve usar CUDA quando disponível"
        else:
            pytest.skip("CUDA não disponível")
    
    def test_xtts_client_cuda_fallback(self):
        """Testa fallback para CPU se CUDA indisponível"""
        import torch
        
        if not torch.cuda.is_available():
            # Se pedir CUDA mas não houver GPU, deve fazer fallback para CPU
            client = XTTSClient(device='cuda', fallback_to_cpu=True)
            assert client.device == 'cpu', "Deve fazer fallback para CPU"
    
    def test_xtts_model_loaded(self):
        """Testa se modelo XTTS foi carregado corretamente"""
        client = XTTSClient(device='cpu')
        
        assert client.tts is not None, "Modelo TTS não foi carregado"
        assert hasattr(client.tts, 'tts_to_file'), "Modelo não tem método tts_to_file"
    
    def test_xtts_supported_languages(self):
        """Testa se português está nas linguagens suportadas"""
        client = XTTSClient(device='cpu')
        
        languages = client.get_supported_languages()
        
        assert 'pt' in languages or 'pt-br' in languages, "Português não suportado!"
        assert len(languages) > 10, "Poucas linguagens suportadas"
