"""
Executor de Testes Reais (test-prod/)

⚠️ ATENÇÃO: Executa testes que chamam SERVIÇOS REAIS
- audio-transcriber API (https://yttranscriber.loadstask.com)
- SubtitleGenerator (VAD real)
- VideoBuilder (FFmpeg burn-in real)

Se qualquer serviço estiver DOWN, testes VÃO FALHAR.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json


class TestRunner:
    """Executa todos os testes reais e gera relatório"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = []
    
    def run_test(self, test_file: str, test_name: str) -> dict:
        """
        Executa um teste e retorna resultado
        
        Returns:
            {
                "test": str,
                "status": "PASSED" | "FAILED",
                "duration_seconds": float,
                "output": str
            }
        """
        print()
        print("="*80)
        print(f"🧪 Executando: {test_name}")
        print("="*80)
        
        start_time = datetime.now()
        
        result = subprocess.run(
            [sys.executable, str(self.test_dir / test_file)],
            capture_output=True,
            text=True
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        status = "PASSED" if result.returncode == 0 else "FAILED"
        
        # Mostrar output do teste
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        print()
        print(f"Status: {status}")
        print(f"Duração: {duration:.2f}s")
        
        return {
            "test": test_name,
            "file": test_file,
            "status": status,
            "duration_seconds": duration,
            "output": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    
    def run_all(self):
        """Executa todos os testes reais"""
        
        print("="*80)
        print("🚀 TEST-PROD - Executando Testes REAIS")
        print("="*80)
        print()
        print("⚠️  ATENÇÃO: Testes chamam serviços REAIS (não mocks)")
        print("   - Se audio-transcriber estiver DOWN, testes vão FALHAR")
        print("   - Se FFmpeg não estiver instalado, testes vão FALHAR")
        print("   - Isso é CORRETO - reflete o que vai acontecer em produção")
        print()
        
        input("Pressione ENTER para continuar...")
        
        # Lista de testes reais
        tests = [
            ("test_real_audio_transcription.py", "Transcrição com Áudio Real"),
            ("test_real_pipeline_complete.py", "Pipeline Completo End-to-End")
        ]
        
        # Executar cada teste
        for test_file, test_name in tests:
            result = self.run_test(test_file, test_name)
            self.results.append(result)
        
        # Relatório final
        self.generate_report()
    
    def generate_report(self):
        """Gera relatório final dos testes"""
        
        print()
        print("="*80)
        print("📊 RELATÓRIO FINAL")
        print("="*80)
        print()
        
        passed = [r for r in self.results if r["status"] == "PASSED"]
        failed = [r for r in self.results if r["status"] == "FAILED"]
        
        total_duration = sum(r["duration_seconds"] for r in self.results)
        
        print(f"Total de testes: {len(self.results)}")
        print(f"✅ Passaram: {len(passed)}")
        print(f"❌ Falharam: {len(failed)}")
        print(f"⏱️  Duração total: {total_duration:.2f}s")
        print()
        
        if passed:
            print("✅ TESTES QUE PASSARAM:")
            for r in passed:
                print(f"   - {r['test']} ({r['duration_seconds']:.2f}s)")
            print()
        
        if failed:
            print("❌ TESTES QUE FALHARAM:")
            for r in failed:
                print(f"   - {r['test']} ({r['duration_seconds']:.2f}s)")
            print()
        
        # Salvar relatório JSON
        results_dir = self.test_dir / "results"
        results_dir.mkdir(exist_ok=True)
        
        report_file = results_dir / f"report_real_tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "passed": len(passed),
            "failed": len(failed),
            "total_duration_seconds": total_duration,
            "tests": self.results
        }
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Relatório salvo: {report_file}")
        print()
        
        # Exit code
        if failed:
            print("="*80)
            print("❌ ALGUNS TESTES FALHARAM")
            print("="*80)
            print()
            print("⚠️  Possíveis causas:")
            print("   1. Serviços de produção estão DOWN")
            print("   2. Rede sem conectividade")
            print("   3. FFmpeg não instalado")
            print("   4. Áudio TEST-.ogg corrompido")
            print()
            print("💡 Se falha aqui, VAI FALHAR EM PRODUÇÃO também!")
            sys.exit(1)
        else:
            print("="*80)
            print("🎉 TODOS OS TESTES PASSARAM")
            print("="*80)
            print()
            print("✅ Sistema está FUNCIONAL em produção")
            print("✅ API audio-transcriber OK")
            print("✅ VAD processing OK")
            print("✅ FFmpeg burn-in OK")
            print()
            print("💡 Sistema PRONTO para deploy!")
            sys.exit(0)


if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all()
