#!/usr/bin/env python3
"""
Script para executar testes do Audio Transcriber Service
"""
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Executa comando e reporta resultado"""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        duration = time.time() - start_time
        
        print(f"✅ Sucesso em {duration:.2f}s")
        if result.stdout:
            print(f"📊 Output:\n{result.stdout}")
            
        return True
        
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        
        print(f"❌ Falhou em {duration:.2f}s")
        if e.stdout:
            print(f"📊 Output:\n{e.stdout}")
        if e.stderr:
            print(f"🚨 Errors:\n{e.stderr}")
            
        return False


def main():
    """Executa suite completa de testes"""
    print("🧪 Audio Transcriber Service - Test Suite")
    print("=" * 60)
    
    if not Path("app").exists():
        print("❌ Execute este script a partir do diretório raiz do serviço")
        sys.exit(1)
    
    test_suites = [
        ("pytest tests/ -v", "Executando todos os testes"),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, description in test_suites:
        if run_command(cmd, description):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print("📈 RELATÓRIO FINAL")
    print(f"{'='*60}")
    print(f"✅ Testes aprovados: {passed}")
    print(f"❌ Testes falhados: {failed}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
