#!/usr/bin/env python3
"""
Script para executar suite completa de testes
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
    print("🧪 Audio Normalization Service - Test Suite")
    print("=" * 60)
    
    # Verifica se estamos no diretório correto
    if not Path("app").exists():
        print("❌ Execute este script a partir do diretório raiz do serviço")
        sys.exit(1)
    
    # Lista de testes para executar
    test_suites = [
        # Testes básicos
        ("pytest tests/test_models.py -v", "Testes dos modelos"),
        ("pytest tests/test_security_validation.py -v", "Testes de segurança e validação"),
        
        # Testes de integração
        ("pytest tests/test_integration.py -v", "Testes de integração"),
        
        # Testes de performance (apenas alguns para não demorar muito)
        ("pytest tests/test_performance.py::TestPerformance::test_concurrent_job_creation -v", "Teste de performance - criação de jobs"),
        ("pytest tests/test_performance.py::TestPerformance::test_rate_limiter_performance -v", "Teste de performance - rate limiter"),
        
        # Testes de carga leves
        ("pytest tests/test_performance.py::TestLoadTesting::test_concurrent_validation -v", "Teste de carga - validação concorrente"),
        
        # Testes de chaos engineering (selecionados)
        ("pytest tests/test_chaos.py::TestChaosEngineering::test_resource_exhaustion_simulation -v", "Chaos engineering - esgotamento de recursos"),
        ("pytest tests/test_chaos.py::TestFailureRecovery::test_timeout_recovery -v", "Teste de recuperação - timeout"),
        
        # Testes de edge cases
        ("pytest tests/test_chaos.py::TestEdgeCases::test_empty_files -v", "Casos extremos - arquivos vazios"),
        ("pytest tests/test_chaos.py::TestEdgeCases::test_unicode_filenames -v", "Casos extremos - nomes unicode"),
    ]
    
    # Executa testes
    passed = 0
    failed = 0
    
    for cmd, description in test_suites:
        if run_command(cmd, description):
            passed += 1
        else:
            failed += 1
    
    # Relatório final
    print(f"\n{'='*60}")
    print("📈 RELATÓRIO FINAL")
    print(f"{'='*60}")
    print(f"✅ Testes aprovados: {passed}")
    print(f"❌ Testes falhados: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 Todos os testes passaram! Sistema está resiliente.")
        return 0
    else:
        success_rate = (passed / (passed + failed)) * 100
        print(f"\n⚠️  Taxa de sucesso: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("📝 Sistema tem boa resiliência, mas precisa de ajustes.")
            return 1
        else:
            print("🚨 Sistema precisa de melhorias críticas de resiliência.")
            return 2


if __name__ == "__main__":
    sys.exit(main())