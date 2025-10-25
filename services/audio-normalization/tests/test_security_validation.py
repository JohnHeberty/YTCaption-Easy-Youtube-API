"""
Testes para validação e segurança de arquivos
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

from fastapi import UploadFile

from app.security_validator import (
    FileValidator, 
    SecurityChecker, 
    ValidationMiddleware,
    FileValidationResult,
    SecurityCheckResult
)
from app.exceptions import RateLimitExceededError


class TestFileValidator:
    """Testes para validação de arquivos"""
    
    @pytest.fixture
    def validator(self):
        return FileValidator()
    
    async def test_valid_mp3_file(self, validator):
        """Testa validação de arquivo MP3 válido"""
        # Simula arquivo MP3 com header válido
        mp3_content = b'\xff\xfb\x90\x00' + b'\x00' * 1000
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.mp3"
        mock_file.read = AsyncMock(return_value=mp3_content)
        mock_file.seek = AsyncMock()
        
        result = await validator.validate_file(mock_file)
        
        assert result.valid is True
        assert result.filename == "test.mp3"
        assert result.size_bytes == len(mp3_content)
        assert len(result.errors) == 0
    
    async def test_invalid_extension(self, validator):
        """Testa arquivo com extensão inválida"""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.exe"
        mock_file.read = AsyncMock(return_value=b"dummy content")
        mock_file.seek = AsyncMock()
        
        result = await validator.validate_file(mock_file)
        
        assert result.valid is False
        assert any("Extensão não permitida" in error for error in result.errors)
    
    async def test_file_too_large(self, validator, test_settings):
        """Testa arquivo muito grande"""
        large_content = b'\xff\xfb\x90\x00' + b'\x00' * (test_settings.processing.max_file_size_mb * 1024 * 1024 + 1)
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "large.mp3"
        mock_file.read = AsyncMock(return_value=large_content)
        mock_file.seek = AsyncMock()
        
        result = await validator.validate_file(mock_file)
        
        assert result.valid is False
        assert any("muito grande" in error for error in result.errors)
    
    async def test_empty_file(self, validator):
        """Testa arquivo vazio"""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "empty.mp3"
        mock_file.read = AsyncMock(return_value=b"")
        mock_file.seek = AsyncMock()
        
        result = await validator.validate_file(mock_file)
        
        assert result.valid is False
        assert any("vazio" in error for error in result.errors)
    
    async def test_suspicious_filename(self, validator):
        """Testa nomes de arquivo suspeitos"""
        suspicious_names = [
            "../../../etc/passwd",
            "test|pipe.mp3",
            "test:colon.mp3",
            "test<redirect.mp3"
        ]
        
        for suspicious_name in suspicious_names:
            mock_file = Mock(spec=UploadFile)
            mock_file.filename = suspicious_name
            mock_file.read = AsyncMock(return_value=b'\xff\xfb\x90\x00' + b'\x00' * 100)
            mock_file.seek = AsyncMock()
            
            result = await validator.validate_file(mock_file)
            
            assert result.valid is False
            assert any("suspeito" in error for error in result.errors)


class TestSecurityChecker:
    """Testes para verificação de segurança"""
    
    @pytest.fixture
    def checker(self):
        return SecurityChecker()
    
    def test_clean_audio_file(self, checker):
        """Testa arquivo de áudio limpo"""
        clean_content = b'\xff\xfb\x90\x00' + b'\x00' * 1000
        
        result = checker.check_file_security(clean_content, "test.mp3")
        
        assert result.safe is True
        assert len(result.threats_detected) == 0
    
    def test_suspicious_patterns(self, checker):
        """Testa detecção de padrões suspeitos"""
        suspicious_content = b'\xff\xfb\x90\x00' + b'#!/bin/bash\necho "hack"' + b'\x00' * 100
        
        result = checker.check_file_security(suspicious_content, "test.mp3")
        
        assert result.safe is False
        assert len(result.threats_detected) > 0
        assert any("Suspicious pattern" in threat for threat in result.threats_detected)
    
    def test_high_entropy(self, checker):
        """Testa detecção de alta entropia"""
        # Cria conteúdo com alta entropia (pseudo-aleatório)
        import random
        random.seed(42)  # Para resultados consistentes
        high_entropy_content = bytes([random.randint(0, 255) for _ in range(10000)])
        
        result = checker.check_file_security(high_entropy_content, "suspicious.mp3")
        
        # Verifica se calculou entropia
        assert result.entropy_score is not None
        assert result.entropy_score > 6.0  # Alta entropia
    
    def test_low_entropy(self, checker):
        """Testa detecção de baixa entropia"""
        # Conteúdo com baixa entropia (muita repetição)
        low_entropy_content = b'\x00' * 10000
        
        result = checker.check_file_security(low_entropy_content, "fake.mp3")
        
        assert result.entropy_score is not None
        assert result.entropy_score < 1.0  # Baixa entropia


class TestRateLimiter:
    """Testes para rate limiter"""
    
    async def test_rate_limit_allows_requests(self):
        """Testa que requests dentro do limite são permitidas"""
        from app.security_validator import RateLimiter
        
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_id = "test_client"
        
        # Primeiras 5 requests devem ser permitidas
        for _ in range(5):
            allowed = await limiter.is_allowed(client_id)
            assert allowed is True
        
        # 6ª request deve ser negada
        allowed = await limiter.is_allowed(client_id)
        assert allowed is False
    
    async def test_rate_limit_window_sliding(self):
        """Testa janela deslizante do rate limiter"""
        from app.security_validator import RateLimiter
        import time
        
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        client_id = "test_client"
        
        # Usa 2 requests
        await limiter.is_allowed(client_id)
        await limiter.is_allowed(client_id)
        
        # 3ª deve ser negada
        allowed = await limiter.is_allowed(client_id)
        assert allowed is False
        
        # Aguarda janela passar
        await asyncio.sleep(1.1)
        
        # Agora deve ser permitida novamente
        allowed = await limiter.is_allowed(client_id)
        assert allowed is True
    
    async def test_remaining_requests(self):
        """Testa contagem de requests restantes"""
        from app.security_validator import RateLimiter
        
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_id = "test_client"
        
        # Inicialmente deve ter 5 disponíveis
        remaining = await limiter.get_remaining_requests(client_id)
        assert remaining == 5
        
        # Usa 2 requests
        await limiter.is_allowed(client_id)
        await limiter.is_allowed(client_id)
        
        # Deve ter 3 restantes
        remaining = await limiter.get_remaining_requests(client_id)
        assert remaining == 3


class TestValidationMiddleware:
    """Testes para middleware de validação"""
    
    @pytest.fixture
    def middleware(self):
        return ValidationMiddleware()
    
    async def test_rate_limit_check(self, middleware):
        """Testa verificação de rate limit"""
        client_id = "test_client"
        
        # Primeiras requests devem passar
        for _ in range(5):
            result = await middleware.check_rate_limit(client_id)
            assert result is True
    
    async def test_rate_limit_exceeded(self, middleware):
        """Testa exceção quando rate limit é excedido"""
        client_id = "test_client"
        
        # Esgota rate limit
        for _ in range(100):  # Bem acima do limite
            try:
                await middleware.check_rate_limit(client_id)
            except RateLimitExceededError:
                break
        
        # Próxima deve gerar exceção
        with pytest.raises(RateLimitExceededError) as exc_info:
            await middleware.check_rate_limit(client_id)
        
        assert exc_info.value.details["client_id"] == client_id
    
    @patch('app.security_validator.FileValidator.validate_file')
    @patch('app.security_validator.SecurityChecker.check_file_security')
    async def test_validate_upload_success(self, mock_security, mock_validation, middleware):
        """Testa validação completa de upload bem-sucedida"""
        # Mock resultados positivos
        mock_validation.return_value = FileValidationResult(
            valid=True,
            filename="test.mp3",
            size_bytes=1000
        )
        
        mock_security.return_value = SecurityCheckResult(safe=True)
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=b"dummy content")
        mock_file.seek = AsyncMock()
        
        file_result, security_result = await middleware.validate_upload(mock_file)
        
        assert file_result.valid is True
        assert security_result.safe is True
        
        # Verifica se métodos foram chamados
        mock_validation.assert_called_once()
        mock_security.assert_called_once()
    
    @patch('app.security_validator.FileValidator.validate_file')
    async def test_validate_upload_file_invalid(self, mock_validation, middleware):
        """Testa comportamento quando arquivo é inválido"""
        # Mock resultado negativo
        mock_validation.return_value = FileValidationResult(
            valid=False,
            filename="invalid.exe",
            size_bytes=1000,
            errors=["Extensão não permitida"]
        )
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=b"dummy content")
        mock_file.seek = AsyncMock()
        
        file_result, security_result = await middleware.validate_upload(mock_file)
        
        assert file_result.valid is False
        assert security_result.safe is False  # Deve marcar como não seguro se arquivo inválido
        assert "File validation failed" in security_result.threats_detected
    
    def test_get_client_id(self, middleware):
        """Testa extração de ID do cliente"""
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock request com IP e User-Agent
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100, 10.0.0.1",
            "User-Agent": "Mozilla/5.0 Test Browser"
        }
        mock_request.client = None
        
        client_id = middleware.get_client_id(mock_request)
        
        # Deve usar o primeiro IP do X-Forwarded-For
        assert client_id.startswith("192.168.1.100")
        assert len(client_id.split("_")) == 2  # IP_hash