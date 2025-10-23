#!/usr/bin/env python
"""
Script para executar suite completa de testes.

Usage:
    python run_tests.py              # Todos os testes
    python run_tests.py --unit       # Apenas testes unitários
    python run_tests.py --integration # Apenas testes de integração
    python run_tests.py --coverage   # Com relatório de cobertura
    python run_tests.py --fast       # Pular testes lentos
"""
import sys
import subprocess
from pathlib import Path


def run_tests(args=None):
    """Executa testes com pytest."""
    base_cmd = ["python", "-m", "pytest"]
    
    # Configurações padrão
    default_args = [
        "-v",  # Verbose
        "--tb=short",  # Traceback curto
        "--strict-markers",  # Markers devem estar registrados
        "-ra",  # Resumo de todos os testes (exceto passed)
    ]
    
    if args is None:
        args = sys.argv[1:]
    
    # Processar argumentos customizados
    custom_args = []
    
    if "--unit" in args:
        custom_args.extend(["tests/unit"])
        args.remove("--unit")
    elif "--integration" in args:
        custom_args.extend(["tests/integration"])
        args.remove("--integration")
    elif "--e2e" in args:
        custom_args.extend(["tests/e2e"])
        args.remove("--e2e")
    else:
        custom_args.extend(["tests/"])
    
    if "--coverage" in args or "--cov" in args:
        custom_args.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term",
            "--cov-report=xml"
        ])
        if "--coverage" in args:
            args.remove("--coverage")
    
    if "--fast" in args:
        custom_args.extend(["-m", "not slow"])
        args.remove("--fast")
    
    if "--no-network" in args:
        custom_args.extend(["-m", "not requires_network"])
        args.remove("--no-network")
    
    # Montar comando final
    final_cmd = base_cmd + default_args + custom_args + args
    
    print(f"🧪 Running tests: {' '.join(final_cmd)}\n")
    
    # Executar
    result = subprocess.run(final_cmd)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
