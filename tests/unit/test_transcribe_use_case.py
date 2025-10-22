"""
Testes unitários para TranscribeYouTubeVideoUseCase.

Testa:
- Fluxo completo de transcrição
- Cache hit (transcrição existente)
- Cache miss (nova transcrição)
- Uso de transcrição do YouTube
- Validação de áudio
- Tratamento de erros
- Integração entre componentes
"""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from pathlib import Path
from datetime import datetime

from src.application.use_cases.transcribe_video import TranscribeYouTubeVideoUseCase
from src.application.dtos.transcription_dtos import (
    TranscribeRequestDTO,
    TranscribeResponseDTO
)
from src.domain.exceptions import (
    VideoDownloadError,
    TranscriptionError,
    ValidationError
)
from src.infrastructure.validators.audio_validator import AudioMetadata


class TestTranscribeYouTubeVideoUseCase:
    """Testa use case de transcrição."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Fixture que cria mocks de todas as dependências."""
        return {
            "video_downloader": Mock(),
            "transcription_service": Mock(),
            "youtube_transcript_service": Mock(),
            "storage_service": Mock(),
            "transcription_cache": Mock(),
            "audio_validator": Mock()
        }
    
    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Fixture que cria instância do use case com mocks."""
        return TranscribeYouTubeVideoUseCase(
            video_downloader=mock_dependencies["video_downloader"],
            transcription_service=mock_dependencies["transcription_service"],
            youtube_transcript_service=mock_dependencies["youtube_transcript_service"],
            storage_service=mock_dependencies["storage_service"],
            transcription_cache=mock_dependencies["transcription_cache"],
            audio_validator=mock_dependencies["audio_validator"]
        )
    
    @pytest.fixture
    def sample_request(self):
        """Fixture que cria request de exemplo."""
        return TranscribeRequestDTO(
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            model_name="base",
            language="en"
        )
    
    @pytest.fixture
    def sample_video_file(self):
        """Fixture que simula VideoFile baixado."""
        mock_video = Mock()
        mock_video.video_id = "dQw4w9WgXcQ"
        mock_video.file_path = "/tmp/video.mp4"
        mock_video.audio_path = "/tmp/audio.mp3"
        mock_video.metadata = {
            "title": "Test Video",
            "duration": 120,
            "channel": "Test Channel"
        }
        return mock_video
    
    @pytest.fixture
    def sample_audio_metadata(self):
        """Fixture que simula AudioMetadata válido."""
        return AudioMetadata(
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
    
    @pytest.fixture
    def sample_transcription_result(self):
        """Fixture que simula resultado de transcrição."""
        return {
            "text": "This is a test transcription",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "text": "This is a test",
                    "confidence": 0.95
                },
                {
                    "id": 1,
                    "start": 5.0,
                    "end": 10.0,
                    "text": "transcription",
                    "confidence": 0.92
                }
            ],
            "language": "en",
            "duration": 120.5
        }
    
    # ========================================
    # TESTES DE CACHE HIT
    # ========================================
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata,
        sample_transcription_result
    ):
        """Testa que cache hit retorna resultado sem reprocessar."""
        # Setup: Video download
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        
        # Setup: Audio validation
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        
        # Setup: Cache HIT (arquivo já transcrito)
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "abc123hash"
        mock_dependencies["transcription_cache"].get.return_value = sample_transcription_result
        
        # Execute
        result = await use_case.execute(sample_request)
        
        # Assert: Deve retornar resultado do cache
        assert isinstance(result, TranscribeResponseDTO)
        assert result.text == "This is a test transcription"
        assert len(result.segments) == 2
        assert result.source == "whisper"
        
        # Assert: NÃO deve chamar transcription_service (cache hit)
        mock_dependencies["transcription_service"].transcribe_audio.assert_not_called()
        
        # Assert: Deve ter chamado cache.get() com 3 parâmetros
        mock_dependencies["transcription_cache"].get.assert_called_once_with(
            file_hash="abc123hash",
            model_name="base",
            language="en"
        )
    
    # ========================================
    # TESTES DE CACHE MISS
    # ========================================
    
    @pytest.mark.asyncio
    async def test_cache_miss_transcribes_and_caches(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata,
        sample_transcription_result
    ):
        """Testa que cache miss processa e salva no cache."""
        # Setup: Video download
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        
        # Setup: Audio validation
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        
        # Setup: Cache MISS (não encontrado)
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "abc123hash"
        mock_dependencies["transcription_cache"].get.return_value = None  # Cache miss
        
        # Setup: YouTube transcript não disponível
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        
        # Setup: Transcription service processa áudio
        mock_dependencies["transcription_service"].transcribe_audio.return_value = sample_transcription_result
        
        # Execute
        result = await use_case.execute(sample_request)
        
        # Assert: Deve retornar resultado da transcrição
        assert isinstance(result, TranscribeResponseDTO)
        assert result.text == "This is a test transcription"
        
        # Assert: Deve ter chamado transcription_service (cache miss)
        mock_dependencies["transcription_service"].transcribe_audio.assert_called_once()
        
        # Assert: Deve ter salvo no cache com 5 parâmetros
        mock_dependencies["transcription_cache"].put.assert_called_once()
        call_args = mock_dependencies["transcription_cache"].put.call_args[1]
        
        assert call_args["file_hash"] == "abc123hash"
        assert call_args["model_name"] == "base"
        assert call_args["language"] == "en"
        assert "transcription_data" in call_args
        assert "file_size_bytes" in call_args
    
    # ========================================
    # TESTES DE YOUTUBE TRANSCRIPT
    # ========================================
    
    @pytest.mark.asyncio
    async def test_uses_youtube_transcript_when_available(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata
    ):
        """Testa que usa transcrição do YouTube quando disponível."""
        # Setup: Video download
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        
        # Setup: Audio validation
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        
        # Setup: Cache MISS
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "abc123hash"
        mock_dependencies["transcription_cache"].get.return_value = None
        
        # Setup: YouTube transcript DISPONÍVEL
        youtube_transcript = {
            "text": "YouTube auto-generated transcript",
            "segments": [{"id": 0, "start": 0.0, "end": 5.0, "text": "Hello"}],
            "language": "en"
        }
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = youtube_transcript
        
        # Execute
        result = await use_case.execute(sample_request)
        
        # Assert: Deve usar transcrição do YouTube
        assert result.text == "YouTube auto-generated transcript"
        assert result.source == "youtube"
        
        # Assert: NÃO deve chamar Whisper (usou YouTube)
        mock_dependencies["transcription_service"].transcribe_audio.assert_not_called()
        
        # Assert: Deve ter salvo no cache mesmo sendo do YouTube
        mock_dependencies["transcription_cache"].put.assert_called_once()
    
    # ========================================
    # TESTES DE VALIDAÇÃO DE ÁUDIO
    # ========================================
    
    @pytest.mark.asyncio
    async def test_audio_validation_failure_raises_error(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file
    ):
        """Testa que falha de validação lança ValidationError."""
        # Setup: Video download
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        
        # Setup: Audio validation FALHOU
        invalid_metadata = AudioMetadata(
            duration_seconds=0.0,
            format_name="unknown",
            codec_name="unknown",
            sample_rate=0,
            channels=0,
            bit_rate=0,
            file_size_bytes=0,
            is_valid=False,
            validation_errors=["Codec not supported", "File corrupted"]
        )
        mock_dependencies["audio_validator"].validate_file.return_value = invalid_metadata
        
        # Execute & Assert: Deve lançar ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await use_case.execute(sample_request)
        
        # Deve conter erros de validação
        assert "Codec not supported" in str(exc_info.value) or \
               "File corrupted" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_audio_validator_called_with_correct_path(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata
    ):
        """Testa que AudioValidator é chamado com path correto."""
        # Setup
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "hash123"
        mock_dependencies["transcription_cache"].get.return_value = {"text": "cached"}
        
        # Execute
        await use_case.execute(sample_request)
        
        # Assert: validate_file chamado SINCRONAMENTE (não await)
        mock_dependencies["audio_validator"].validate_file.assert_called_once()
        
        # Assert: Chamado com Path object do audio_path
        call_args = mock_dependencies["audio_validator"].validate_file.call_args[0]
        assert str(call_args[0]) == sample_video_file.audio_path
    
    @pytest.mark.asyncio
    async def test_audio_validator_returns_dataclass_not_dict(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata
    ):
        """Testa que código usa AudioMetadata como dataclass (não dict)."""
        # Setup
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "hash123"
        mock_dependencies["transcription_cache"].get.return_value = {"text": "cached"}
        
        # Execute: Não deve lançar erro de acesso a atributos
        result = await use_case.execute(sample_request)
        
        # Assert: Executou com sucesso (sem TypeError de dict access)
        assert result is not None
    
    # ========================================
    # TESTES DE TRATAMENTO DE ERROS
    # ========================================
    
    @pytest.mark.asyncio
    async def test_invalid_youtube_url_raises_error(
        self,
        use_case,
        mock_dependencies
    ):
        """Testa que URL inválida lança VideoDownloadError."""
        # Setup: Downloader lança erro de URL inválida
        mock_dependencies["video_downloader"].download.side_effect = VideoDownloadError(
            "Invalid YouTube URL"
        )
        
        request = TranscribeRequestDTO(
            youtube_url="https://invalid.url/watch?v=xxx",
            model_name="base",
            language="en"
        )
        
        # Execute & Assert
        with pytest.raises(VideoDownloadError):
            await use_case.execute(request)
    
    @pytest.mark.asyncio
    async def test_video_download_error_raises_error(
        self,
        use_case,
        mock_dependencies,
        sample_request
    ):
        """Testa que erro de download lança VideoDownloadError."""
        # Setup: Download falha
        mock_dependencies["video_downloader"].download.side_effect = VideoDownloadError(
            "Failed to download video"
        )
        
        # Execute & Assert
        with pytest.raises(VideoDownloadError):
            await use_case.execute(sample_request)
    
    @pytest.mark.asyncio
    async def test_transcription_error_propagates(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata
    ):
        """Testa que erro de transcrição é propagado."""
        # Setup
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "hash123"
        mock_dependencies["transcription_cache"].get.return_value = None
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        
        # Setup: Transcription falha
        mock_dependencies["transcription_service"].transcribe_audio.side_effect = TranscriptionError(
            "Whisper model failed"
        )
        
        # Execute & Assert
        with pytest.raises(TranscriptionError):
            await use_case.execute(sample_request)
    
    # ========================================
    # TESTES DE INTEGRAÇÃO ENTRE COMPONENTES
    # ========================================
    
    @pytest.mark.asyncio
    async def test_full_transcription_flow_cache_miss(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata,
        sample_transcription_result
    ):
        """Testa fluxo completo: download → validação → cache miss → transcrição → cache."""
        # Setup: Todas as etapas
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["audio_validator"].estimate_processing_time.return_value = 30.0
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "file_hash_123"
        mock_dependencies["transcription_cache"].get.return_value = None  # Cache miss
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        mock_dependencies["transcription_service"].transcribe_audio.return_value = sample_transcription_result
        
        # Execute
        result = await use_case.execute(sample_request)
        
        # Assert: Ordem de chamadas
        assert mock_dependencies["video_downloader"].download.called
        assert mock_dependencies["audio_validator"].validate_file.called
        assert mock_dependencies["transcription_cache"].compute_file_hash.called
        assert mock_dependencies["transcription_cache"].get.called
        assert mock_dependencies["youtube_transcript_service"].get_transcript.called
        assert mock_dependencies["transcription_service"].transcribe_audio.called
        assert mock_dependencies["transcription_cache"].put.called
        
        # Assert: Resultado correto
        assert result.text == "This is a test transcription"
        assert result.source == "whisper"
        assert result.video_id == "dQw4w9WgXcQ"
    
    @pytest.mark.asyncio
    async def test_cache_get_called_with_three_parameters(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata
    ):
        """Testa que cache.get() é chamado com exatamente 3 parâmetros."""
        # Setup
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "hash_abc"
        mock_dependencies["transcription_cache"].get.return_value = None
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        mock_dependencies["transcription_service"].transcribe_audio.return_value = {"text": "test"}
        
        # Execute
        await use_case.execute(sample_request)
        
        # Assert: Chamado com file_hash, model_name, language
        mock_dependencies["transcription_cache"].get.assert_called_once_with(
            file_hash="hash_abc",
            model_name="base",
            language="en"
        )
    
    @pytest.mark.asyncio
    async def test_cache_put_called_with_five_parameters(
        self,
        use_case,
        mock_dependencies,
        sample_request,
        sample_video_file,
        sample_audio_metadata,
        sample_transcription_result
    ):
        """Testa que cache.put() é chamado com exatamente 5 parâmetros."""
        # Setup
        mock_dependencies["video_downloader"].download.return_value = sample_video_file
        mock_dependencies["audio_validator"].validate_file.return_value = sample_audio_metadata
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "hash_xyz"
        mock_dependencies["transcription_cache"].get.return_value = None
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        mock_dependencies["transcription_service"].transcribe_audio.return_value = sample_transcription_result
        
        # Execute
        await use_case.execute(sample_request)
        
        # Assert: Chamado com 5 parâmetros nomeados
        call_kwargs = mock_dependencies["transcription_cache"].put.call_args[1]
        
        assert "file_hash" in call_kwargs
        assert "transcription_data" in call_kwargs
        assert "model_name" in call_kwargs
        assert "language" in call_kwargs
        assert "file_size_bytes" in call_kwargs
        
        assert call_kwargs["file_hash"] == "hash_xyz"
        assert call_kwargs["model_name"] == "base"
        assert call_kwargs["language"] == "en"


class TestTranscribeYouTubeVideoUseCaseEdgeCases:
    """Testa casos extremos do use case."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Fixture com mocks."""
        return {
            "video_downloader": Mock(),
            "transcription_service": Mock(),
            "youtube_transcript_service": Mock(),
            "storage_service": Mock(),
            "transcription_cache": Mock(),
            "audio_validator": Mock()
        }
    
    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Fixture do use case."""
        return TranscribeYouTubeVideoUseCase(
            video_downloader=mock_dependencies["video_downloader"],
            transcription_service=mock_dependencies["transcription_service"],
            youtube_transcript_service=mock_dependencies["youtube_transcript_service"],
            storage_service=mock_dependencies["storage_service"],
            transcription_cache=mock_dependencies["transcription_cache"],
            audio_validator=mock_dependencies["audio_validator"]
        )
    
    @pytest.mark.asyncio
    async def test_different_languages_use_different_cache(
        self,
        use_case,
        mock_dependencies
    ):
        """Testa que idiomas diferentes usam cache keys diferentes."""
        # Setup mocks básicos
        mock_video = Mock()
        mock_video.audio_path = "/tmp/audio.mp3"
        mock_dependencies["video_downloader"].download.return_value = mock_video
        
        mock_audio = AudioMetadata(
            duration_seconds=120.0,
            format_name="mp4",
            codec_name="aac",
            sample_rate=44100,
            channels=2,
            bit_rate=128000,
            file_size_bytes=10485760,
            is_valid=True,
            validation_errors=[]
        )
        mock_dependencies["audio_validator"].validate_file.return_value = mock_audio
        
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "same_hash"
        mock_dependencies["transcription_cache"].get.return_value = None
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        mock_dependencies["transcription_service"].transcribe_audio.return_value = {"text": "test"}
        
        # Request em inglês
        request_en = TranscribeRequestDTO(
            youtube_url="https://youtube.com/watch?v=xxx",
            model_name="base",
            language="en"
        )
        
        await use_case.execute(request_en)
        
        # Verificar cache.get() com "en"
        call_1 = mock_dependencies["transcription_cache"].get.call_args
        assert call_1[1]["language"] == "en"
        
        # Request em português
        request_pt = TranscribeRequestDTO(
            youtube_url="https://youtube.com/watch?v=xxx",
            model_name="base",
            language="pt"
        )
        
        await use_case.execute(request_pt)
        
        # Verificar cache.get() com "pt"
        call_2 = mock_dependencies["transcription_cache"].get.call_args
        assert call_2[1]["language"] == "pt"
    
    @pytest.mark.asyncio
    async def test_different_models_use_different_cache(
        self,
        use_case,
        mock_dependencies
    ):
        """Testa que modelos diferentes usam cache keys diferentes."""
        # Setup mocks básicos
        mock_video = Mock()
        mock_video.audio_path = "/tmp/audio.mp3"
        mock_dependencies["video_downloader"].download.return_value = mock_video
        
        mock_audio = AudioMetadata(
            duration_seconds=120.0,
            format_name="mp4",
            codec_name="aac",
            sample_rate=44100,
            channels=2,
            bit_rate=128000,
            file_size_bytes=10485760,
            is_valid=True,
            validation_errors=[]
        )
        mock_dependencies["audio_validator"].validate_file.return_value = mock_audio
        
        mock_dependencies["transcription_cache"].compute_file_hash.return_value = "same_hash"
        mock_dependencies["transcription_cache"].get.return_value = None
        mock_dependencies["youtube_transcript_service"].get_transcript.return_value = None
        mock_dependencies["transcription_service"].transcribe_audio.return_value = {"text": "test"}
        
        # Request com modelo "base"
        request_base = TranscribeRequestDTO(
            youtube_url="https://youtube.com/watch?v=xxx",
            model_name="base",
            language="en"
        )
        
        await use_case.execute(request_base)
        
        call_1 = mock_dependencies["transcription_cache"].get.call_args
        assert call_1[1]["model_name"] == "base"
        
        # Request com modelo "small"
        request_small = TranscribeRequestDTO(
            youtube_url="https://youtube.com/watch?v=xxx",
            model_name="small",
            language="en"
        )
        
        await use_case.execute(request_small)
        
        call_2 = mock_dependencies["transcription_cache"].get.call_args
        assert call_2[1]["model_name"] == "small"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
