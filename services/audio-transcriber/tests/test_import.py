"""
Teste simples de importação dos novos módulos.

Este teste verifica se os módulos recém-criados podem ser importados
corretamente, sem depender de infraestrutura (Redis, etc).
"""
import sys
from pathlib import Path

# Adiciona o diretório app ao path (não o package app)
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Bypass app/__init__.py que carrega main.py
import importlib.util

def test_import_module(module_name, module_path):
    """Importa um módulo específico sem carregar dependências."""
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).parent.parent / module_path
    )
    module = importlib.util.module_from_spec(spec)
    # Não executa ainda - só verifica se existe
    return spec is not None


def test_validators_import():
    """Testa importação do módulo validators."""
    from core.validators import (
        ValidationError,
        JobIdValidator,
        LanguageValidator,
        EngineValidator,
        FileValidator,
        TranscriptionRequestValidator,
    )
    print("✓ core.validators import OK")
    return True


def test_interfaces_import():
    """Testa importação do módulo interfaces."""
    from domain.interfaces import (
        TranscriptionResult,
        TranscriptionEngine,
        IModelManager,
    )
    print("✓ domain.interfaces import OK")
    return True


def test_whisper_engine_import():
    """Testa importação do módulo whisper_engine."""
    # Este módulo tem dependências pesadas (torch), então verificamos
    # apenas se o arquivo existe e tem sintaxe válida
    import ast
    
    engine_path = Path(__file__).parent.parent / "app" / "infrastructure" / "whisper_engine.py"
    with open(engine_path) as f:
        source = f.read()
    
    # Verifica sintaxe Python
    ast.parse(source)
    print("✓ infrastructure.whisper_engine.py syntax OK")
    return True


def test_transcription_service_import():
    """Testa importação do serviço de transcrição."""
    import ast
    
    service_path = Path(__file__).parent.parent / "app" / "services" / "transcription_service.py"
    with open(service_path) as f:
        source = f.read()
    
    ast.parse(source)
    print("✓ services.transcription_service.py syntax OK")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testes de Importação - Audio Transcriber")
    print("=" * 60)
    
    results = []
    
    # Testes que não dependem de infraestrutura
    try:
        results.append(("validators", test_validators_import()))
    except Exception as e:
        print(f"✗ validators import FAILED: {e}")
        results.append(("validators", False))
    
    try:
        results.append(("interfaces", test_interfaces_import()))
    except Exception as e:
        print(f"✗ interfaces import FAILED: {e}")
        results.append(("interfaces", False))
    
    try:
        results.append(("whisper_engine", test_whisper_engine_import()))
    except Exception as e:
        print(f"✗ whisper_engine import FAILED: {e}")
        results.append(("whisper_engine", False))
    
    try:
        results.append(("transcription_service", test_transcription_service_import()))
    except Exception as e:
        print(f"✗ transcription_service import FAILED: {e}")
        results.append(("transcription_service", False))
    
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"Resultados: {passed}/{total} testes passaram")
    
    if passed == total:
        print("✓ Todos os testes passaram!")
        exit(0)
    else:
        print("✗ Alguns testes falharam")
        exit(1)
