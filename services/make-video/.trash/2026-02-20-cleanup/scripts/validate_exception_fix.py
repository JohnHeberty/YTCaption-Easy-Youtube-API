#!/usr/bin/env python3
"""
Script de validação da correção do bug de Exception Details Conflict.

Este script verifica se as correções foram aplicadas corretamente no código
e valida que as exceções podem ser instanciadas sem causar TypeError.

Uso:
    python validate_exception_fix.py
"""

import sys
import inspect
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "app"))


def check_base_exception_signature():
    """Verifica se MakeVideoBaseException aceita **kwargs."""
    from app.shared.exceptions_v2 import MakeVideoBaseException
    
    sig = inspect.signature(MakeVideoBaseException.__init__)
    params = list(sig.parameters.keys())
    
    print("✓ Verificando assinatura de MakeVideoBaseException...")
    print(f"  Parâmetros: {', '.join(params)}")
    
    if 'kwargs' in params:
        print("  ✅ **kwargs presente")
        return True
    else:
        print("  ❌ **kwargs ausente (BUG NÃO CORRIGIDO!)")
        return False


def check_external_service_exception():
    """Verifica se ExternalServiceException usa kwargs.pop()."""
    from app.shared.exceptions_v2 import ExternalServiceException
    
    print("\n✓ Verificando ExternalServiceException...")
    
    # Test instantiation
    try:
        exc = ExternalServiceException(
            service_name="test-service",
            message="Test error",
            error_code="TEST_ERROR"
        )
        print(f"  ✅ Instanciação básica OK")
        print(f"  ✅ details['service'] = {exc.details.get('service')}")
        return True
    except TypeError as e:
        print(f"  ❌ Erro ao instanciar: {e}")
        return False


def test_transcriber_unavailable_exception():
    """Testa TranscriberUnavailableException (caso do bug original)."""
    from app.shared.exceptions_v2 import TranscriberUnavailableException
    
    print("\n✓ Testando TranscriberUnavailableException...")
    
    # Cenário 1: Sem details= (USO CORRETO)
    try:
        exc1 = TranscriberUnavailableException(
            reason="Transcription job failed: timeout"
        )
        print("  ✅ Instanciação SEM details= OK")
        print(f"     message: {exc1.message}")
        print(f"     service: {exc1.details.get('service')}")
        print(f"     recoverable: {exc1.recoverable}")
    except Exception as e:
        print(f"  ❌ Erro (cenário 1): {e}")
        return False
    
    # Cenário 2: Com cause
    try:
        import requests
        base_error = requests.exceptions.Timeout("Connection timeout")
        exc2 = TranscriberUnavailableException(
            reason="Failed to check transcription status",
            cause=base_error
        )
        print("  ✅ Instanciação com cause OK")
        print(f"     cause type: {type(exc2.cause).__name__}")
    except Exception as e:
        print(f"  ❌ Erro (cenário 2): {e}")
        return False
    
    return True


def test_audio_exceptions():
    """Testa exceções de áudio (AudioNotFoundException, etc)."""
    from app.shared.exceptions_v2 import (
        AudioNotFoundException,
        AudioCorruptedException,
        AudioTooShortException
    )
    
    print("\n✓ Testando Audio Exceptions...")
    
    try:
        exc1 = AudioNotFoundException(audio_path="/tmp/test.mp3")
        print(f"  ✅ AudioNotFoundException OK")
        print(f"     audio_path: {exc1.details.get('audio_path')}")
        
        exc2 = AudioCorruptedException(
            audio_path="/tmp/corrupt.mp3",
            reason="Invalid header"
        )
        print(f"  ✅ AudioCorruptedException OK")
        print(f"     reason: {exc2.details.get('reason')}")
        
        exc3 = AudioTooShortException(duration=1.5, min_duration=3.0)
        print(f"  ✅ AudioTooShortException OK")
        print(f"     duration: {exc3.details.get('duration')}")
        
        return True
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def test_serialization():
    """Testa serialização de exceções."""
    from app.shared.exceptions_v2 import TranscriberUnavailableException
    
    print("\n✓ Testando serialização...")
    
    try:
        exc = TranscriberUnavailableException(
            reason="Test error",
            job_id="test_job_123"
        )
        
        result = exc.to_dict()
        
        print("  ✅ Serialização via to_dict() OK")
        print(f"     Keys: {', '.join(result.keys())}")
        
        assert "error" in result
        assert "message" in result
        assert "details" in result
        assert "service" in result["details"]
        
        print("  ✅ Estrutura do dict validada")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def check_api_client_file():
    """Verifica se api_client.py não tem mais details= nas chamadas."""
    print("\n✓ Verificando api_client.py...")
    
    api_client_path = Path(__file__).parent / "app" / "api" / "api_client.py"
    
    if not api_client_path.exists():
        print(f"  ⚠️  Arquivo não encontrado: {api_client_path}")
        return None
    
    content = api_client_path.read_text()
    lines = content.split('\n')
    
    # Procurar por TranscriberUnavailableException com details=
    issues = []
    for i, line in enumerate(lines, 1):
        if 'TranscriberUnavailableException' in line:
            # Check next 5 lines for details=
            chunk = '\n'.join(lines[i:i+5])
            if 'details=' in chunk and 'details={' in chunk:
                issues.append(f"Linha {i}: Possível uso de details= explícito")
    
    if issues:
        print("  ⚠️  Possíveis problemas encontrados:")
        for issue in issues:
            print(f"     {issue}")
        return False
    else:
        print("  ✅ Nenhum uso incorreto de details= encontrado")
        return True


def print_summary(results):
    """Imprime resumo dos testes."""
    print("\n" + "="*60)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    for test_name, result in results.items():
        icon = "✅" if result is True else "❌" if result is False else "⚠️"
        status = "PASS" if result is True else "FAIL" if result is False else "SKIP"
        print(f"{icon} {test_name}: {status}")
    
    print("-"*60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    if failed == 0:
        print("\n🎉 TODAS AS VALIDAÇÕES PASSARAM!")
        print("✅ A correção do bug foi aplicada corretamente.")
        return 0
    else:
        print(f"\n❌ {failed} VALIDAÇÃO(ÕES) FALHARAM!")
        print("⚠️  A correção pode estar incompleta.")
        return 1


def main():
    """Executa todos os testes de validação."""
    print("🔍 Validando correção do bug: Exception Details Conflict")
    print("="*60)
    
    results = {}
    
    # Run all checks
    results["Base Exception Signature"] = check_base_exception_signature()
    results["ExternalServiceException"] = check_external_service_exception()
    results["TranscriberUnavailableException"] = test_transcriber_unavailable_exception()
    results["Audio Exceptions"] = test_audio_exceptions()
    results["Exception Serialization"] = test_serialization()
    results["API Client File Check"] = check_api_client_file()
    
    # Print summary and exit with appropriate code
    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
