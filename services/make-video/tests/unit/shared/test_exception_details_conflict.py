"""
Teste para bug de múltiplos valores para 'details' em TranscriptionTimeoutException

Bug Report:
- Job ID: 76kUcvmUNS5ZKAKrvy8umv
- Error: "app.shared.exceptions_v2.MakeVideoBaseException.__init__() got multiple values for keyword argument 'details'"
- Progress: 75%
- Audio duration: 33.322167s

Root Cause:
1. TranscriptionTimeoutException passou details= explicitamente
2. ExternalServiceException também manipulava details em **kwargs
3. Resultado: details passado duas vezes para MakeVideoBaseException.__init__()

Fix:
1. Corrigir chamada de TranscriptionTimeoutException em api_client.py
2. Corrigir ExternalServiceException para usar pop() em vez de modificar **kwargs
"""
import pytest
from app.shared.exceptions_v2 import (
    TranscriptionTimeoutException,
    APIRateLimitException,
    CircuitBreakerOpenException,
    ExternalServiceException,
    ErrorCode
)


class TestExceptionDetailsConflict:
    """Testes para prevenir conflito de 'details' em exceções"""
    
    def test_transcription_timeout_exception_no_details_conflict(self):
        """
        Teste: TranscriptionTimeoutException não deve causar conflito de details
        
        BUG: api_client.py chamava TranscriptionTimeoutException(timeout_seconds=..., details={...})
        FIX: Agora chama TranscriptionTimeoutException(job_id=..., max_polls=...)
        """
        # Test 1: Argumentos corretos (como deveria ser)
        exc = TranscriptionTimeoutException(
            job_id="test-job-123",
            max_polls=60
        )
        
        assert exc.message == "Transcription timeout: job test-job-123 (max polls: 60)"
        assert exc.error_code == ErrorCode.API_TIMEOUT
        assert exc.details["transcription_job_id"] == "test-job-123"
        assert exc.details["max_polls"] == 60
        assert exc.details["service"] == "audio-transcriber"
    
    def test_transcription_timeout_with_extra_kwargs(self):
        """
        Teste: TranscriptionTimeoutException com kwargs extras (cause, job_id, etc)
        """
        original_error = Exception("Network timeout")
        
        exc = TranscriptionTimeoutException(
            job_id="test-job-456",
            max_polls=30,
            cause=original_error,
            recoverable=True
        )
        
        assert exc.cause == original_error
        assert exc.job_id is None  # job_id específico do make-video não setado
        assert exc.recoverable == True
        assert exc.details["service"] == "audio-transcriber"
    
    def test_api_rate_limit_exception_no_details_conflict(self):
        """
        Teste: APIRateLimitException também passava details= explicitamente
        """
        exc = APIRateLimitException(
            service_name="youtube-search",
            retry_after=60
        )
        
        assert exc.message == "Rate limit exceeded: youtube-search (retry after 60s)"
        assert exc.error_code == ErrorCode.API_RATE_LIMIT
        assert exc.details["retry_after"] == 60
        assert exc.details["service"] == "youtube-search"
        assert exc.recoverable == True
    
    def test_circuit_breaker_exception_no_details_conflict(self):
        """
        Teste: CircuitBreakerOpenException também passava details= explicitamente
        """
        exc = CircuitBreakerOpenException(
            service_name="video-downloader"
        )
        
        assert exc.message == "Circuit breaker OPEN for video-downloader"
        assert exc.error_code == ErrorCode.CIRCUIT_BREAKER_OPEN
        assert exc.details["circuit_state"] == "open"
        assert exc.details["service"] == "video-downloader"
        assert exc.recoverable == False
    
    def test_external_service_exception_details_merge(self):
        """
        Teste: ExternalServiceException deve mesclar details corretamente
        
        - Se details= não for passado, cria um vazio
        - Se details= for passado, adiciona 'service' nele
        - Nunca causa conflito com **kwargs
        """
        # Caso 1: Sem details
        exc1 = ExternalServiceException(
            "test-service",
            "Test message",
            ErrorCode.API_INVALID_RESPONSE
        )
        assert exc1.details == {"service": "test-service"}
        
        # Caso 2: Com details explícito
        exc2 = ExternalServiceException(
            "test-service",
            "Test message",
            ErrorCode.API_INVALID_RESPONSE,
            details={"custom_key": "custom_value"}
        )
        assert exc2.details == {
            "custom_key": "custom_value",
            "service": "test-service"
        }
    
    def test_exception_serialization(self):
        """
        Teste: Exceção deve serializar corretamente para dict (usado em API responses)
        """
        exc = TranscriptionTimeoutException(
            job_id="serialize-test",
            max_polls=45
        )
        
        result = exc.to_dict()
        
        assert result["error"] == "TranscriptionTimeoutException"
        assert result["message"] == "Transcription timeout: job serialize-test (max polls: 45)"
        assert result["error_code"] == ErrorCode.API_TIMEOUT.value
        assert result["error_code_name"] == "API_TIMEOUT"
        assert result["details"]["transcription_job_id"] == "serialize-test"
        assert result["details"]["max_polls"] == 45
        assert result["details"]["service"] == "audio-transcriber"
        assert result["job_id"] is None  # job_id do make-video não setado
        assert result["recoverable"] == False
        assert "timestamp" in result
    
    def test_regression_original_bug(self):
        """
        Teste de regressão: Reproduzir exatamente o bug original
        
        Bug original em api_client.py linha 447-452:
        ```python
        raise TranscriptionTimeoutException(
            timeout_seconds=max_polls * poll_interval,  # ERRO: argumento errado
            details={                                   # ERRO: details duplicado
                "job_id": job_id,
                "max_polls": max_polls
            }
        )
        ```
        
        Este teste verifica que a nova implementação funciona corretamente
        """
        # Simular o que o código estava tentando fazer
        job_id = "76kUcvmUNS5ZKAKrvy8umv"
        max_polls = 60
        poll_interval = 5
        
        # Código CORRETO (após fix)
        exc = TranscriptionTimeoutException(
            job_id=job_id,
            max_polls=max_polls
        )
        
        # Verificações
        assert exc.message == f"Transcription timeout: job {job_id} (max polls: {max_polls})"
        assert exc.error_code == ErrorCode.API_TIMEOUT
        assert exc.details["transcription_job_id"] == job_id
        assert exc.details["max_polls"] == max_polls
        assert exc.details["service"] == "audio-transcriber"
        
        # Deve serializar sem erros
        result = exc.to_dict()
        assert result["error"] == "TranscriptionTimeoutException"
        assert result["job_id"] is None  # job_id do make-video, não o transcription job_id
    
    def test_all_external_service_exceptions_work(self):
        """
        Teste: Todas as subclasses de ExternalServiceException devem funcionar
        """
        from app.shared.exceptions_v2 import (
            YouTubeSearchUnavailableException,
            VideoDownloaderUnavailableException,
            TranscriberUnavailableException
        )
        
        # YouTubeSearchUnavailableException
        exc1 = YouTubeSearchUnavailableException(reason="Service down")
        assert exc1.details["service"] == "youtube-search"
        assert exc1.recoverable == True
        
        # VideoDownloaderUnavailableException
        exc2 = VideoDownloaderUnavailableException(reason="Network error")
        assert exc2.details["service"] == "video-downloader"
        assert exc2.recoverable == True
        
        # TranscriberUnavailableException
        exc3 = TranscriberUnavailableException(reason="API error")
        assert exc3.details["service"] == "audio-transcriber"
        assert exc3.recoverable == True
        
        # Todas devem serializar sem erros
        for exc in [exc1, exc2, exc3]:
            result = exc.to_dict()
            assert "error" in result
            assert "details" in result
            assert "service" in result["details"]
    
    def test_exception_with_details_conflict_scenario(self):
        """
        Teste: Reproduzir cenário exato que causa o bug em produção
        
        Cenário:
        1. TranscriberUnavailableException era chamado com details= explícito (ERRADO)
        2. Após o fix, não deve mais passar details= via kwargs
        3. A exceção cria details internamente via ExternalServiceException
        """
        from app.shared.exceptions_v2 import TranscriberUnavailableException
        
        # Chamada CORRETA (após fix)
        exc = TranscriberUnavailableException(
            reason="Transcription job failed: timeout"
        )
        
        # Deve funcionar normalmente
        assert exc.message == "Audio transcriber unavailable: Transcription job failed: timeout"
        assert exc.details["service"] == "audio-transcriber"
        assert exc.recoverable == True
    
    def test_all_audio_exceptions_without_details_kwarg(self):
        """
        Teste: Todas as exceções de áudio funcionam SEM passar details= via kwargs
        
        IMPORTANTE: As exceções já criam details internamente.
        Passar details= via kwargs causa conflito e é um uso incorreto da API.
        """
        from app.shared.exceptions_v2 import (
            AudioNotFoundException,
            AudioCorruptedException,
            AudioInvalidFormatException,
            AudioTooShortException,
            AudioTooLongException
        )
        
        # Uso CORRETO (sem details= via kwargs)
        exc1 = AudioNotFoundException(audio_path="/tmp/test.mp3")
        assert exc1.details["audio_path"] == "/tmp/test.mp3"
        
        exc2 = AudioCorruptedException(
            audio_path="/tmp/corrupt.mp3",
            reason="Invalid header"
        )
        assert exc2.details["audio_path"] == "/tmp/corrupt.mp3"
        assert exc2.details["reason"] == "Invalid header"
        
        exc3 = AudioTooShortException(duration=1.5, min_duration=3.0)
        assert exc3.details["duration"] == 1.5
        assert exc3.details["min_duration"] == 3.0
        
        # Todas devem serializar sem erros
        for exc in [exc1, exc2, exc3]:
            result = exc.to_dict()
            assert "error" in result
            assert "details" in result
