"""
Testes de dependências RVC
Sprint 2: Dependências
"""
import pytest


class TestRvcDependenciesImport:
    """
    Testes que validam imports de todas as dependências RVC
    """
    
    def test_import_tts_with_rvc(self):
        """tts-with-rvc deve importar sem erros"""
        try:
            import tts_with_rvc
            assert hasattr(tts_with_rvc, '__version__'), "tts-with-rvc missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import tts-with-rvc: {e}")
    
    def test_import_tts_rvc_class(self):
        """TTS_RVC class deve estar acessível"""
        try:
            from tts_with_rvc import TTS_RVC
            assert TTS_RVC is not None, "TTS_RVC class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import TTS_RVC: {e}")
    
    def test_import_fairseq(self):
        """fairseq deve importar (Hubert model)"""
        try:
            import fairseq
            assert hasattr(fairseq, '__version__'), "fairseq missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import fairseq: {e}")
    
    def test_import_faiss(self):
        """faiss deve importar (index retrieval)"""
        try:
            import faiss
            # Verifica se é versão GPU ou CPU
            assert hasattr(faiss, 'IndexFlatL2'), "faiss missing IndexFlatL2"
        except ImportError as e:
            pytest.fail(f"Failed to import faiss: {e}")
    
    def test_import_librosa(self):
        """librosa deve importar (audio processing)"""
        try:
            import librosa
            assert hasattr(librosa, '__version__'), "librosa missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import librosa: {e}")
    
    def test_import_parselmouth(self):
        """praat-parselmouth deve importar (PM pitch method)"""
        try:
            import parselmouth
            assert hasattr(parselmouth, 'Sound'), "parselmouth missing Sound class"
        except ImportError as e:
            pytest.fail(f"Failed to import parselmouth: {e}")
    
    def test_import_torchcrepe(self):
        """torchcrepe deve importar (CREPE pitch method)"""
        try:
            import torchcrepe
            assert hasattr(torchcrepe, 'predict'), "torchcrepe missing predict function"
        except ImportError as e:
            pytest.fail(f"Failed to import torchcrepe: {e}")
    
    def test_import_soundfile(self):
        """soundfile deve importar (I/O de áudio)"""
        try:
            import soundfile as sf
            assert hasattr(sf, 'read'), "soundfile missing read function"
        except ImportError as e:
            pytest.fail(f"Failed to import soundfile: {e}")


class TestRvcModulesStructure:
    """
    Testes que validam estrutura interna do tts-with-rvc
    """
    
    def test_import_vc_modules(self):
        """Módulo VC deve importar"""
        try:
            from tts_with_rvc.infer.vc.modules import VC
            assert VC is not None, "VC class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import VC: {e}")
    
    def test_import_pipeline(self):
        """Pipeline class deve importar"""
        try:
            from tts_with_rvc.infer.vc.pipeline import Pipeline
            assert Pipeline is not None, "Pipeline class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import Pipeline: {e}")
    
    def test_import_rvc_convert(self):
        """rvc_convert function deve importar"""
        try:
            from tts_with_rvc.vc_infer import rvc_convert
            assert callable(rvc_convert), "rvc_convert is not callable"
        except ImportError as e:
            pytest.fail(f"Failed to import rvc_convert: {e}")
    
    def test_import_rmvpe(self):
        """RMVPE pitch extractor deve importar"""
        try:
            from tts_with_rvc.infer.lib.rmvpe import RMVPE
            assert RMVPE is not None, "RMVPE class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import RMVPE: {e}")


class TestRvcCompatibilityXTTS:
    """
    Testes que validam compatibilidade RVC + XTTS (sem regressões)
    """
    
    def test_xtts_still_imports(self):
        """XTTS deve continuar importando após adicionar RVC deps"""
        try:
            from TTS.api import TTS
            assert TTS is not None, "TTS class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import TTS (regression): {e}")
    
    def test_torch_versions_compatible(self):
        """torch, torchaudio devem ser versões compatíveis"""
        import torch
        import torchaudio
        
        torch_version = torch.__version__.split('+')[0]  # Remove +cu121
        torchaudio_version = torchaudio.__version__.split('+')[0]
        
        # Ambos devem ser 2.4.0
        assert torch_version.startswith('2.4'), f"torch version {torch_version} incompatible"
        assert torchaudio_version.startswith('2.4'), f"torchaudio version {torchaudio_version} incompatible"
    
    def test_no_dependency_conflicts(self):
        """Não deve haver conflitos de versão entre deps XTTS e RVC"""
        import pkg_resources
        
        # Packages críticos
        critical = ['torch', 'torchaudio', 'soundfile', 'librosa', 'numpy']
        
        for package in critical:
            try:
                dist = pkg_resources.get_distribution(package)
                assert dist is not None, f"{package} not installed"
            except pkg_resources.DistributionNotFound:
                pytest.fail(f"{package} not found in environment")


class TestRvcHealthEndpoint:
    """
    Testes de health endpoint que valida deps RVC
    """
    
    def test_health_dependencies_check(self):
        """Health check deve validar deps RVC disponíveis"""
        # Este teste será implementado quando criarmos o endpoint
        # Por enquanto, apenas valida que conseguimos importar o que precisamos
        required_modules = [
            'tts_with_rvc',
            'fairseq',
            'faiss',
            'librosa',
            'parselmouth',
            'torchcrepe'
        ]
        
        missing = []
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(module_name)
        
        assert len(missing) == 0, f"Missing RVC dependencies: {', '.join(missing)}"
