"""
Teste simples de importação dos novos módulos (sem dependências externas).
"""
import sys
import ast
from pathlib import Path

# Configuração de path
APP_DIR = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP_DIR.parent))
sys.path.insert(0, str(APP_DIR))

def check_syntax(filepath):
    """Verifica sintaxe de um arquivo Python."""
    try:
        with open(filepath) as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, str(e)

def check_imports():
    """Verifica imports básicos."""
    results = []
    
    # Check 1: Validators syntax
    validators_path = APP_DIR / "core" / "validators.py"
    ok, err = check_syntax(validators_path)
    results.append(("core/validators.py syntax", ok, err))
    
    # Check 2: Whisper engine syntax
    engine_path = APP_DIR / "infrastructure" / "whisper_engine.py"
    ok, err = check_syntax(engine_path)
    results.append(("infrastructure/whisper_engine.py syntax", ok, err))
    
    # Check 3: Transcription service syntax
    service_path = APP_DIR / "services" / "transcription_service.py"
    ok, err = check_syntax(service_path)
    results.append(("services/transcription_service.py syntax", ok, err))
    
    # Check 4: Interfaces imports
    try:
        from domain.interfaces import TranscriptionResult, TranscriptionEngine
        results.append(("domain.interfaces import", True, None))
    except Exception as e:
        results.append(("domain.interfaces import", False, str(e)))
    
    # Check 5: Check file existence
    files_to_check = [
        APP_DIR / "core" / "validators.py",
        APP_DIR / "infrastructure" / "whisper_engine.py",
        APP_DIR / "services" / "transcription_service.py",
        APP_DIR / "domain" / "interfaces.py",
    ]
    
    for fpath in files_to_check:
        exists = fpath.exists()
        results.append((f"File exists: {fpath.name}", exists, None))
    
    return results

if __name__ == "__main__":
    print("=" * 70)
    print("Validação de Arquivos - Audio Transcriber Sprints")
    print("=" * 70)
    
    results = check_imports()
    
    for name, ok, err in results:
        status = "✓" if ok else "✗"
        print(f"{status} {name}")
        if err:
            print(f"  Error: {err}")
    
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"Resultados: {passed}/{total} verificações passaram")
    
    if passed == total:
        print("✓ TODAS AS VERIFICAÇÕES PASSARAM!")
        exit(0)
    else:
        print("✗ Algumas verificações falharam")
        exit(1)
