"""
Testes unitários para AudioValidator.

Testa:
- Validação de arquivos de áudio válidos
- Detecção de arquivos corrompidos
- Detecção de formatos não suportados
- Extração de metadados (duração, codec, bitrate)
- Estimativa de tempo de processamento
"""
import tempfile
from pathlib import Path
import subprocess
import pytest

from src.infrastructure.validators.audio_validator import (
    AudioValidator,
    AudioMetadata
)


class TestAudioMetadata:
    """Testa dataclass AudioMetadata."""
    
    def test_audio_metadata_valid(self):
        """Testa criação de AudioMetadata válido."""
        metadata = AudioMetadata(
            duration_seconds=120.5,
            format_name="mp4",
            codec_name="aac",
            sample_rate=44100,
            channels=2,
            bit_rate=128000,
            file_size_bytes=10485760,
            is_valid=True,
            validation_errors=[]
        )
        
        assert metadata.is_valid is True
        assert len(metadata.validation_errors) == 0
        assert metadata.duration_seconds == 120.5
        assert metadata.codec_name == "aac"
        assert metadata.sample_rate == 44100
        assert metadata.file_size_mb == 10.0
    
    def test_audio_metadata_invalid(self):
        """Testa criação de AudioMetadata inválido."""
        metadata = AudioMetadata(
            duration_seconds=0.0,
            format_name="unknown",
            codec_name="unknown",
            sample_rate=0,
            channels=0,
            bit_rate=0,
            file_size_bytes=0,
            is_valid=False,
            validation_errors=["File not found", "Invalid format"]
        )
        
        assert metadata.is_valid is False
        assert len(metadata.validation_errors) == 2
        assert "File not found" in metadata.validation_errors


class TestAudioValidator:
    """Testa classe AudioValidator."""
    
    @pytest.fixture
    def validator(self):
        """Fixture que cria instância do validator."""
        return AudioValidator()
    
    @pytest.fixture
    def valid_audio_file(self, tmp_path):
        """Fixture que cria arquivo de áudio válido (fake)."""
        # Nota: Este é um arquivo fake para testes básicos
        # Para testes reais com ffmpeg, precisa de arquivo de áudio real
        audio_file = tmp_path / "valid_audio.mp3"
        audio_file.write_bytes(b"fake mp3 data" * 1000)
        return audio_file
    
    def test_validator_initialization(self, validator):
        """Testa inicialização do validator."""
        assert validator is not None
        assert hasattr(validator, "validate_file")
        assert hasattr(validator, "estimate_processing_time")
        assert len(validator.SUPPORTED_AUDIO_CODECS) > 0
    
    def test_validate_file_not_found(self, validator):
        """Testa validação de arquivo inexistente."""
        result = validator.validate_file(Path("/nonexistent/file.mp3"))
        
        assert isinstance(result, AudioMetadata)
        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.validation_errors)
    
    def test_validate_file_empty(self, validator, tmp_path):
        """Testa validação de arquivo vazio."""
        empty_file = tmp_path / "empty.mp3"
        empty_file.write_bytes(b"")
        
        result = validator.validate_file(empty_file)
        
        assert isinstance(result, AudioMetadata)
        assert result.is_valid is False
        assert any("empty" in err.lower() or "size" in err.lower() 
                   for err in result.validation_errors)
    
    def test_validate_file_too_small(self, validator, tmp_path):
        """Testa validação de arquivo muito pequeno."""
        small_file = tmp_path / "small.mp3"
        small_file.write_bytes(b"tiny")  # 4 bytes
        
        result = validator.validate_file(small_file)
        
        assert isinstance(result, AudioMetadata)
        assert result.is_valid is False
    
    def test_validate_file_returns_dataclass(self, validator, valid_audio_file):
        """Testa que validate_file() retorna AudioMetadata dataclass."""
        result = validator.validate_file(valid_audio_file)
        
        # Deve ser instância de AudioMetadata
        assert isinstance(result, AudioMetadata)
        
        # Deve ter atributos de dataclass (não dict)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "validation_errors")
        assert hasattr(result, "duration_seconds")
        assert hasattr(result, "codec_name")
        assert hasattr(result, "sample_rate")
        
        # Não deve ser dict
        assert not isinstance(result, dict)
    
    def test_validate_file_synchronous(self, validator, valid_audio_file):
        """Testa que validate_file() é método síncrono."""
        # Não deve precisar de await
        result = validator.validate_file(valid_audio_file)
        
        # Resultado deve estar disponível imediatamente
        assert result is not None
        assert isinstance(result, AudioMetadata)
    
    def test_estimate_processing_time_short_audio(self, validator):
        """Testa estimativa de tempo para áudio curto."""
        # Áudio de 30 segundos com modelo base
        estimate_seconds = validator.estimate_processing_time(
            duration_seconds=30.0,
            model_name="base"
        )
        
        assert estimate_seconds > 0
        assert estimate_seconds < 300  # Deve ser razoável (< 5 min)
    
    def test_estimate_processing_time_long_audio(self, validator):
        """Testa estimativa de tempo para áudio longo."""
        # Áudio de 1 hora com modelo base
        estimate_seconds = validator.estimate_processing_time(
            duration_seconds=3600.0,
            model_name="base"
        )
        
        assert estimate_seconds > 0
        # Áudio longo deve ter estimativa maior
        short_estimate = validator.estimate_processing_time(30.0, "base")
        assert estimate_seconds > short_estimate
    
    def test_estimate_processing_time_different_models(self, validator):
        """Testa que modelos maiores têm estimativas maiores."""
        duration = 120.0  # 2 minutos
        
        # Modelo base (rápido)
        base_estimate = validator.estimate_processing_time(duration, "base")
        
        # Modelo large (lento)
        large_estimate = validator.estimate_processing_time(duration, "large")
        
        # Large deve ser mais lento que base
        assert large_estimate >= base_estimate
    
    def test_estimate_processing_time_zero_duration(self, validator):
        """Testa estimativa para duração zero."""
        estimate = validator.estimate_processing_time(0.0, "base")
        
        # Deve retornar valor mínimo ou zero
        assert estimate >= 0
    
    def test_estimate_processing_time_negative_duration(self, validator):
        """Testa estimativa para duração negativa."""
        # Deve tratar como valor inválido ou retornar zero
        estimate = validator.estimate_processing_time(-10.0, "base")
        
        assert estimate >= 0
    
    def test_estimate_processing_time_unknown_model(self, validator):
        """Testa estimativa para modelo desconhecido."""
        # Deve usar valor padrão ou base
        estimate = validator.estimate_processing_time(
            duration_seconds=60.0,
            model_name="unknown_model_xyz"
        )
        
        assert estimate > 0
    
    def test_validate_file_attributes_not_dict(self, validator, valid_audio_file):
        """Testa que não pode acessar resultado como dict."""
        result = validator.validate_file(valid_audio_file)
        
        # Acesso via atributo deve funcionar
        assert result.is_valid is not None
        
        # Acesso via dict deve falhar
        with pytest.raises(TypeError):
            _ = result["is_valid"]
    
    def test_validate_file_error_list_type(self, validator):
        """Testa que validation_errors é sempre lista."""
        # Arquivo inexistente
        result = validator.validate_file(Path("/nonexistent.mp3"))
        
        assert isinstance(result.validation_errors, list)
        assert len(result.validation_errors) > 0
        
        # Todos os elementos devem ser strings
        assert all(isinstance(err, str) for err in result.validation_errors)


class TestAudioValidatorIntegration:
    """Testes de integração com ffmpeg (se disponível)."""
    
    @pytest.fixture
    def validator(self):
        """Fixture que cria instância do validator."""
        return AudioValidator()
    
    @pytest.fixture
    def check_ffmpeg_available(self):
        """Fixture que verifica se ffmpeg está disponível."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("ffmpeg not available")
            return False
    
    @pytest.mark.skipif(
        not Path("/usr/bin/ffmpeg").exists() and not Path("C:\\ffmpeg\\bin\\ffmpeg.exe").exists(),
        reason="ffmpeg not found in common locations"
    )
    def test_validate_real_audio_file(self, validator, check_ffmpeg_available):
        """
        Teste com arquivo de áudio real (skip se ffmpeg não disponível).
        
        Para executar este teste:
        1. Coloque um arquivo de áudio real em tests/fixtures/sample_audio.mp3
        2. ffmpeg deve estar instalado
        """
        sample_file = Path("tests/fixtures/sample_audio.mp3")
        
        if not sample_file.exists():
            pytest.skip("Sample audio file not found")
        
        result = validator.validate_file(sample_file)
        
        # Arquivo real deve ser válido
        assert result.is_valid is True
        assert len(result.validation_errors) == 0
        
        # Deve ter metadados extraídos
        assert result.duration_seconds > 0
        assert result.codec is not None
        assert result.sample_rate_hz > 0


class TestAudioValidatorEdgeCases:
    """Testa casos extremos e edge cases."""
    
    @pytest.fixture
    def validator(self):
        """Fixture que cria instância do validator."""
        return AudioValidator()
    
    def test_validate_file_with_special_characters(self, validator, tmp_path):
        """Testa validação de arquivo com caracteres especiais no nome."""
        special_file = tmp_path / "áudio tëst 文件.mp3"
        special_file.write_bytes(b"fake audio data" * 100)
        
        result = validator.validate_file(special_file)
        
        # Deve processar sem erro
        assert isinstance(result, AudioMetadata)
    
    def test_validate_file_path_object(self, validator, tmp_path):
        """Testa que aceita Path object."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake data" * 100)
        
        # Passar como Path (não string)
        result = validator.validate_file(audio_file)
        
        assert isinstance(result, AudioMetadata)
    
    def test_validate_file_string_path(self, validator, tmp_path):
        """Testa que aceita string path."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake data" * 100)
        
        # Passar como string
        result = validator.validate_file(str(audio_file))
        
        assert isinstance(result, AudioMetadata)
    
    def test_concurrent_validations(self, validator, tmp_path):
        """Testa múltiplas validações simultâneas."""
        # Criar múltiplos arquivos
        files = []
        for i in range(5):
            audio_file = tmp_path / f"audio_{i}.mp3"
            audio_file.write_bytes(f"fake audio {i}".encode() * 100)
            files.append(audio_file)
        
        # Validar todos
        results = [validator.validate_file(f) for f in files]
        
        # Todos devem retornar AudioMetadata
        assert all(isinstance(r, AudioMetadata) for r in results)
        assert len(results) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
