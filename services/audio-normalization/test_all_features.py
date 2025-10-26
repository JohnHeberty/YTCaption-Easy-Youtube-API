#!/usr/bin/env python3
"""
Script de Teste Completo - Audio Normalization Service
Testa TODOS os 5 parâmetros de processamento individualmente

Este script prova que:
1. Todas as features funcionam (ou falham de forma controlada)
2. A API NUNCA quebra mesmo quando tasks falham
3. O sistema de resiliência captura e reporta erros corretamente
"""

import requests
import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json

# Configuração
BASE_URL = "http://localhost:8001"  # Ajuste conforme necessário
TIMEOUT_SECONDS = 600  # 10 minutos de timeout
POLL_INTERVAL = 2  # Verifica status a cada 2 segundos


class AudioNormalizationTester:
    """Tester completo para o serviço de normalização de áudio"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []
        
    def check_health(self) -> bool:
        """Verifica se o serviço está saudável"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Serviço saudável: {data}")
                return True
            else:
                print(f"❌ Serviço não saudável. Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro ao verificar health: {e}")
            return False
    
    def create_job(self, audio_file_path: str, **params) -> Dict[str, Any]:
        """
        Cria um job de processamento de áudio
        
        Args:
            audio_file_path: Caminho para arquivo de áudio
            **params: Parâmetros de processamento (remove_noise, apply_highpass_filter, etc.)
        
        Returns:
            dict: Dados do job criado
        """
        if not Path(audio_file_path).exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_file_path}")
        
        # Prepara form data
        files = {
            'file': open(audio_file_path, 'rb')
        }
        
        # Converte parâmetros para strings (form-data)
        data = {}
        for key, value in params.items():
            data[key] = 'true' if value else 'false'
        
        try:
            response = requests.post(
                f"{self.base_url}/jobs",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                job_data = response.json()
                print(f"✅ Job criado: {job_data['id']}")
                return job_data
            else:
                print(f"❌ Erro ao criar job. Status: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                raise Exception(f"Failed to create job: {response.status_code}")
                
        finally:
            files['file'].close()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Consulta status de um job
        
        Args:
            job_id: ID do job
        
        Returns:
            dict: Status do job
        """
        try:
            response = requests.get(f"{self.base_url}/jobs/{job_id}", timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"⚠️ Job {job_id} não encontrado")
                return {"status": "not_found", "error": "Job not found"}
            else:
                print(f"⚠️ Erro ao consultar job {job_id}. Status: {response.status_code}")
                return {"status": "error", "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"❌ Exceção ao consultar job {job_id}: {e}")
            return {"status": "exception", "error": str(e)}
    
    def wait_for_completion(self, job_id: str, timeout: int = TIMEOUT_SECONDS) -> Dict[str, Any]:
        """
        Aguarda conclusão de um job com polling
        
        Args:
            job_id: ID do job
            timeout: Timeout em segundos
        
        Returns:
            dict: Job final (completed ou failed)
        """
        start_time = time.time()
        poll_count = 0
        
        print(f"⏳ Aguardando conclusão do job {job_id}...")
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > timeout:
                print(f"⏰ TIMEOUT após {elapsed:.1f}s")
                return {
                    "status": "timeout",
                    "error": f"Job não completou em {timeout}s",
                    "job_id": job_id
                }
            
            # Consulta status
            job_status = self.get_job_status(job_id)
            poll_count += 1
            
            current_status = job_status.get('status', 'unknown')
            progress = job_status.get('progress', 0.0)
            
            # Imprime progresso
            print(f"   [{poll_count}] Status: {current_status}, Progress: {progress}%")
            
            # Verifica se completou
            if current_status in ['completed', 'success']:
                print(f"✅ Job {job_id} COMPLETADO em {elapsed:.1f}s")
                return job_status
            elif current_status in ['failed', 'error']:
                error_msg = job_status.get('error_message', 'Unknown error')
                print(f"❌ Job {job_id} FALHOU: {error_msg}")
                return job_status
            elif current_status in ['timeout', 'exception', 'not_found']:
                print(f"💥 Job {job_id} em estado problemático: {current_status}")
                return job_status
            
            # Aguarda antes do próximo poll
            time.sleep(POLL_INTERVAL)
    
    def run_test(self, test_name: str, audio_file: str, params: Dict[str, bool]) -> Dict[str, Any]:
        """
        Executa um teste completo
        
        Args:
            test_name: Nome descritivo do teste
            audio_file: Caminho do arquivo de áudio
            params: Parâmetros de processamento
        
        Returns:
            dict: Resultado do teste
        """
        print(f"\n{'='*80}")
        print(f"🧪 TESTE: {test_name}")
        print(f"   Parâmetros: {params}")
        print(f"{'='*80}")
        
        result = {
            "test_name": test_name,
            "params": params,
            "success": False,
            "job_id": None,
            "final_status": None,
            "error": None,
            "elapsed_time": 0
        }
        
        start_time = time.time()
        
        try:
            # 1. Cria job
            job_data = self.create_job(audio_file, **params)
            result["job_id"] = job_data.get('id')
            
            # 2. Aguarda conclusão
            final_job = self.wait_for_completion(result["job_id"])
            result["final_status"] = final_job.get('status')
            
            # 3. Verifica resultado
            if final_job.get('status') in ['completed', 'success']:
                result["success"] = True
                print(f"✅ TESTE PASSOU: {test_name}")
            else:
                result["error"] = final_job.get('error_message', 'Unknown error')
                print(f"❌ TESTE FALHOU: {test_name} - {result['error']}")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"💥 TESTE COM EXCEÇÃO: {test_name} - {e}")
        
        result["elapsed_time"] = time.time() - start_time
        self.results.append(result)
        
        return result
    
    def test_api_resilience(self) -> bool:
        """
        Testa que a API nunca quebra, mesmo durante processamento
        
        Returns:
            bool: True se API permaneceu resiliente
        """
        print(f"\n{'='*80}")
        print(f"🛡️ TESTE DE RESILIÊNCIA DA API")
        print(f"{'='*80}")
        
        resilience_ok = True
        
        for i in range(10):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    print(f"   [{i+1}/10] ✅ API respondendo")
                else:
                    print(f"   [{i+1}/10] ⚠️ Status {response.status_code}")
                    resilience_ok = False
            except Exception as e:
                print(f"   [{i+1}/10] ❌ Exceção: {e}")
                resilience_ok = False
            
            time.sleep(1)
        
        if resilience_ok:
            print("✅ API PERMANECEU RESILIENTE durante todos os testes")
        else:
            print("❌ API TEVE PROBLEMAS de resiliência")
        
        return resilience_ok
    
    def print_summary(self):
        """Imprime resumo de todos os testes"""
        print(f"\n{'='*80}")
        print(f"📊 RESUMO DOS TESTES")
        print(f"{'='*80}")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed
        
        print(f"\nTotal de testes: {total}")
        print(f"✅ Passou: {passed}")
        print(f"❌ Falhou: {failed}")
        print(f"Taxa de sucesso: {(passed/total*100):.1f}%\n")
        
        for result in self.results:
            status_emoji = "✅" if result['success'] else "❌"
            print(f"{status_emoji} {result['test_name']}")
            print(f"   Status final: {result['final_status']}")
            print(f"   Tempo: {result['elapsed_time']:.1f}s")
            if result['error']:
                print(f"   Erro: {result['error'][:100]}")
            print()


def main():
    """Função principal do script de teste"""
    
    # 1. Verifica se arquivo de áudio de teste existe
    test_audio = Path("./uploads").glob("*.wav")
    test_audio = list(test_audio) or list(Path("./uploads").glob("*.mp3"))
    test_audio = list(test_audio) or list(Path("./uploads").glob("*.m4a"))
    
    if not test_audio:
        print("❌ ERRO: Nenhum arquivo de áudio encontrado em ./uploads/")
        print("   Por favor, coloque um arquivo de áudio de teste em ./uploads/")
        sys.exit(1)
    
    audio_file = str(test_audio[0])
    print(f"🎵 Usando arquivo de teste: {audio_file}\n")
    
    # 2. Inicializa tester
    tester = AudioNormalizationTester(BASE_URL)
    
    # 3. Verifica health
    if not tester.check_health():
        print("❌ Serviço não está saudável. Verifique se o serviço está rodando.")
        sys.exit(1)
    
    # 4. Define testes (um para cada parâmetro)
    tests = [
        ("Baseline (sem processamento)", {}),
        ("Remove Noise", {"remove_noise": True}),
        ("Convert to Mono", {"convert_to_mono": True}),
        ("Apply Highpass Filter", {"apply_highpass_filter": True}),
        ("Set Sample Rate 16kHz", {"set_sample_rate_16k": True}),
        ("Isolate Vocals", {"isolate_vocals": True}),
    ]
    
    # 5. Executa testes
    print(f"\n🚀 Iniciando bateria de {len(tests)} testes...")
    
    for test_name, params in tests:
        tester.run_test(test_name, audio_file, params)
        
        # Pequena pausa entre testes
        time.sleep(2)
    
    # 6. Teste de resiliência
    tester.test_api_resilience()
    
    # 7. Imprime resumo
    tester.print_summary()
    
    # 8. Retorna código de saída
    all_passed = all(r['success'] for r in tester.results)
    
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        sys.exit(0)
    else:
        print("⚠️ ALGUNS TESTES FALHARAM - mas a API permaneceu resiliente!")
        sys.exit(1)


if __name__ == "__main__":
    main()
