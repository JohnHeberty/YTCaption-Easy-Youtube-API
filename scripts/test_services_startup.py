#!/usr/bin/env python3
"""
Script de teste de startup dos serviços
Valida que todos os serviços podem inicializar corretamente
"""

import sys
import os
import subprocess
from pathlib import Path

# Cores para output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*80}{NC}")
    print(f"{BLUE}{text}{NC}")
    print(f"{BLUE}{'='*80}{NC}\n")

def print_test(text):
    print(f"{BLUE}▶{NC} {text}")

def print_success(text):
    print(f"{GREEN}✅ {text}{NC}")

def print_error(text):
    print(f"{RED}❌ {text}{NC}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{NC}")

def test_python_imports(service_name, service_path):
    """Testa se os imports Python funcionam"""
    print_test(f"Testando imports do {service_name}")
    
    # Adiciona o path do serviço e common ao PYTHONPATH
    env = os.environ.copy()
    common_path = str(Path(__file__).parent.parent / "common")
    env['PYTHONPATH'] = f"{service_path}:{common_path}:{env.get('PYTHONPATH', '')}"
    
    # Lista de arquivos Python para testar
    py_files = []
    app_dir = Path(service_path) / "app"
    if app_dir.exists():
        py_files = list(app_dir.glob("*.py"))
    
    errors = []
    for py_file in py_files:
        if py_file.name == "__pycache__":
            continue
            
        # Tenta compilar o arquivo
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(py_file)],
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode != 0:
            errors.append(f"{py_file.name}: {result.stderr}")
    
    if errors:
        print_error(f"Erros de sintaxe encontrados em {service_name}:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print_success(f"Sintaxe Python OK em {service_name}")
        return True

def test_imports_runtime(service_name, service_path):
    """Testa imports em runtime"""
    print_test(f"Testando imports em runtime do {service_name}")
    
    # Cria script de teste temporário
    test_script = f"""
import sys
sys.path.insert(0, '{service_path}')
sys.path.insert(0, '{Path(__file__).parent.parent / "common"}')

try:
    # Tenta importar os módulos principais
    from app import main
    from app import config
    from app import redis_store
    print("IMPORTS_OK")
except Exception as e:
    print(f"IMPORT_ERROR: {{e}}")
    import traceback
    traceback.print_exc()
"""
    
    result = subprocess.run(
        ["python3", "-c", test_script],
        capture_output=True,
        text=True,
        cwd=service_path
    )
    
    if "IMPORTS_OK" in result.stdout:
        print_success(f"Imports em runtime OK em {service_name}")
        return True
    else:
        print_error(f"Erro ao importar módulos de {service_name}:")
        print(result.stdout)
        print(result.stderr)
        return False

def test_common_library():
    """Testa a biblioteca common"""
    print_header("Testando Biblioteca Common")
    
    common_path = Path(__file__).parent.parent / "common"
    
    # Testa imports da biblioteca common
    test_script = f"""
import sys
sys.path.insert(0, '{common_path}')

errors = []

try:
    from common.models.base import BaseJob, JobStatus, HealthStatus
    print("✓ common.models.base")
except Exception as e:
    errors.append(f"common.models.base: {{e}}")

try:
    from common.logging.structured import setup_structured_logging
    print("✓ common.logging.structured")
except Exception as e:
    errors.append(f"common.logging.structured: {{e}}")

try:
    from common.redis.resilient_store import ResilientRedisStore
    print("✓ common.redis.resilient_store")
except Exception as e:
    errors.append(f"common.redis.resilient_store: {{e}}")

try:
    from common.exceptions.handlers import setup_exception_handlers
    print("✓ common.exceptions.handlers")
except Exception as e:
    errors.append(f"common.exceptions.handlers: {{e}}")

try:
    from common.config.base_settings import BaseServiceSettings
    print("✓ common.config.base_settings")
except Exception as e:
    errors.append(f"common.config.base_settings: {{e}}")

if errors:
    print("\\nERROS:")
    for error in errors:
        print(f"  ❌ {{error}}")
    sys.exit(1)
else:
    print("\\n✅ COMMON_LIBRARY_OK")
"""
    
    result = subprocess.run(
        ["python3", "-c", test_script],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if "COMMON_LIBRARY_OK" in result.stdout:
        print_success("Biblioteca common OK")
        return True
    else:
        print_error("Erro na biblioteca common:")
        print(result.stderr)
        return False

def main():
    print_header("🧪 TESTE DE STARTUP DOS SERVIÇOS")
    
    root_path = Path(__file__).parent.parent
    
    # Serviços para testar (excluindo transcriber)
    services = {
        "audio-normalization": root_path / "services" / "audio-normalization",
        "video-downloader": root_path / "services" / "video-downloader",
        "youtube-search": root_path / "services" / "youtube-search",
        "orchestrator": root_path / "orchestrator"
    }
    
    results = {}
    
    # Teste 1: Common library
    results['common'] = test_common_library()
    
    # Teste 2: Cada serviço
    for service_name, service_path in services.items():
        print_header(f"Testando {service_name}")
        
        if not service_path.exists():
            print_warning(f"Path não encontrado: {service_path}")
            results[service_name] = False
            continue
        
        # Teste de sintaxe
        syntax_ok = test_python_imports(service_name, str(service_path))
        
        # Teste de imports runtime
        runtime_ok = test_imports_runtime(service_name, str(service_path))
        
        results[service_name] = syntax_ok and runtime_ok
    
    # Resumo
    print_header("📊 RESUMO DOS TESTES")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for service, status in results.items():
        if status:
            print_success(f"{service}: PASSOU")
        else:
            print_error(f"{service}: FALHOU")
    
    print(f"\n{BLUE}Total:{NC} {total}")
    print(f"{GREEN}Passou:{NC} {passed}")
    print(f"{RED}Falhou:{NC} {failed}")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\n{BLUE}Taxa de sucesso:{NC} {success_rate:.1f}%")
    
    if failed == 0:
        print(f"\n{GREEN}{'='*80}{NC}")
        print(f"{GREEN}🎉 TODOS OS TESTES PASSARAM!{NC}")
        print(f"{GREEN}{'='*80}{NC}\n")
        return 0
    else:
        print(f"\n{YELLOW}{'='*80}{NC}")
        print(f"{YELLOW}⚠️  ALGUNS TESTES FALHARAM{NC}")
        print(f"{YELLOW}{'='*80}{NC}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
