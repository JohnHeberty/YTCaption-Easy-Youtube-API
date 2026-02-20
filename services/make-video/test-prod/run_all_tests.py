"""
Run All Tests - Test-Prod

Executa todos os testes de produção e gera relatório
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json


async def run_test(test_file: Path) -> dict:
    """
    Executa um teste e retorna resultado
    
    Returns:
        dict com:
        - test_name: Nome do teste
        - passed: Se passou
        - duration: Duração em segundos
        - output: Output do teste
    """
    
    start_time = datetime.now()
    
    print(f"\n🧪 Executando: {test_file.name}...")
    print("="*80)
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(test_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    stdout, _ = await proc.communicate()
    output = stdout.decode()
    
    duration = (datetime.now() - start_time).total_seconds()
    passed = proc.returncode == 0
    
    print(output)
    
    return {
        'test_name': test_file.stem,
        'test_file': str(test_file),
        'passed': passed,
        'duration': duration,
        'returncode': proc.returncode,
        'output_lines': len(output.split('\n'))
    }


async def main():
    """Executar todos os testes"""
    
    test_dir = Path(__file__).parent
    
    # Encontrar todos os testes
    test_files = sorted(test_dir.glob("test_*.py"))
    
    if not test_files:
        print("❌ Nenhum teste encontrado em test-prod/")
        return 1
    
    print("="*80)
    print(f"🚀 TEST-PROD: Executando {len(test_files)} testes")
    print("="*80)
    print(f"📁 Diretório: {test_dir}")
    print(f"🕐 Início: {datetime.now()}")
    print()
    
    for test_file in test_files:
        print(f"   - {test_file.name}")
    
    print("="*80)
    
    # Executar testes
    results = []
    
    for test_file in test_files:
        result = await run_test(test_file)
        results.append(result)
    
    # Gerar relatório
    print("\n" + "="*80)
    print("📊 RELATÓRIO FINAL")
    print("="*80)
    
    passed_count = sum(1 for r in results if r['passed'])
    failed_count = len(results) - passed_count
    total_duration = sum(r['duration'] for r in results)
    
    print(f"\n✅ Passed: {passed_count}/{len(results)}")
    print(f"❌ Failed: {failed_count}/{len(results)}")
    print(f"⏱️  Total duration: {total_duration:.2f}s")
    
    print("\n📋 Detalhes:\n")
    
    for result in results:
        status = "✅" if result['passed'] else "❌"
        print(f"{status} {result['test_name']}")
        print(f"   Duration: {result['duration']:.2f}s")
        print(f"   Output: {result['output_lines']} lines")
        if not result['passed']:
            print(f"   Return code: {result['returncode']}")
        print()
    
    # Salvar relatório JSON
    report_file = test_dir / "results" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.parent.mkdir(exist_ok=True)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_tests': len(results),
        'passed': passed_count,
        'failed': failed_count,
        'total_duration': total_duration,
        'results': results
    }
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Relatório salvo: {report_file}")
    
    # Decisão
    print("\n" + "="*80)
    
    if failed_count == 0:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("\n📋 Próximos passos:")
        print("   1. ✅ Revisar relatório JSON")
        print("   2. ⏭️  Mover testes aprovados para tests/")
        print("   3. ⏭️  Integrar melhorias M1-M5 no código principal")
        print("   4. 🗑️  Mover test-prod/ para .trash/ (após integração)")
        return 0
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("\n🔧 Ações necessárias:")
        print("   1. Revisar logs de erro acima")
        print("   2. Corrigir problemas identificados")
        print("   3. Re-executar testes")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
