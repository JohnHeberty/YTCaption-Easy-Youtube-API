#!/usr/bin/env python3
"""
Script de teste para o serviço Audio Normalization
Testa cada parâmetro booleano individualmente
"""
import pytest
pytestmark = pytest.mark.skip(reason="DEPRECATED: imports removed legacy modules. See PLAN.md F2-T8.")
import requests
import time
import os
import sys
from pathlib import Path


class AudioNormalizationTester:
    def __init__(self, base_url="http://localhost:8002"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_health(self):
        """Testa endpoint de health"""
        print("🔍 Testando health endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            print(f"✅ Health OK: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ Health failed: {e}")
            return False
    
    def upload_file_and_test(self, audio_file_path, test_name, **params):
        """
        Faz upload do arquivo e testa processamento
        
        Args:
            audio_file_path: Caminho para arquivo de áudio
            test_name: Nome do teste
            **params: Parâmetros booleanos para processamento
        """
        print(f"\n🧪 {test_name}")
        print(f"📁 Arquivo: {audio_file_path}")
        print(f"⚙️  Parâmetros: {params}")
        
        if not os.path.exists(audio_file_path):
            print(f"❌ Arquivo não encontrado: {audio_file_path}")
            return None
        
        try:
            # Faz upload
            with open(audio_file_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_file_path), f, 'audio/webm')}
                data = params
                
                response = self.session.post(
                    f"{self.base_url}/jobs",
                    files=files,
                    data=data
                )
            
            response.raise_for_status()
            job = response.json()
            job_id = job['id']
            
            print(f"✅ Job criado: {job_id}")
            print(f"📊 Status inicial: {job['status']}")
            
            # Monitora progresso
            return self.monitor_job(job_id, test_name)
            
        except Exception as e:
            print(f"❌ Erro no upload: {e}")
            if hasattr(e, 'response'):
                print(f"   Resposta: {e.response.text}")
            return None
    
    def monitor_job(self, job_id, test_name, max_wait_seconds=300):
        """Monitora progresso do job"""
        print(f"⏳ Monitorando job {job_id}...")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            try:
                response = self.session.get(f"{self.base_url}/jobs/{job_id}")
                response.raise_for_status()
                job = response.json()
                
                status = job['status']
                progress = job.get('progress', 0)
                
                print(f"   Status: {status} | Progresso: {progress:.1f}%")
                
                if status == 'completed':
                    print(f"✅ {test_name} - CONCLUÍDO!")
                    print(f"   📄 Arquivo de saída: {job.get('output_file', 'N/A')}")
                    print(f"   📏 Tamanho entrada: {job.get('file_size_input', 0)} bytes")
                    print(f"   📏 Tamanho saída: {job.get('file_size_output', 0)} bytes")
                    return job
                
                elif status == 'failed':
                    print(f"❌ {test_name} - FALHOU!")
                    print(f"   Erro: {job.get('error_message', 'Erro desconhecido')}")
                    return job
                
                elif status in ['queued', 'processing']:
                    time.sleep(2)  # Aguarda 2 segundos
                    continue
                
            except Exception as e:
                print(f"❌ Erro ao consultar job: {e}")
                break
        
        print(f"⏰ Timeout aguardando {test_name}")
        return None
    
    def run_all_tests(self, audio_file_path):
        """Executa todos os testes"""
        print("🚀 Iniciando testes do Audio Normalization Service")
        print("=" * 60)
        
        # Testa health primeiro
        if not self.test_health():
            print("❌ Serviço não está funcionando. Verifique se está rodando.")
            return
        
        # Lista de testes - cada um testa um parâmetro específico
        tests = [
            {
                'name': 'Teste 1: Apenas salvar arquivo (padrão)',
                'params': {}
            },
            {
                'name': 'Teste 2: Remover ruído',
                'params': {'remove_noise': True}
            },
            {
                'name': 'Teste 3: Converter para mono',
                'params': {'convert_to_mono': True}
            },
            {
                'name': 'Teste 4: Aplicar filtro high-pass',
                'params': {'apply_highpass_filter': True}
            },
            {
                'name': 'Teste 5: Definir sample rate para 16kHz',
                'params': {'set_sample_rate_16k': True}
            },
            {
                'name': 'Teste 6: Isolar vocais (OpenUnmix)',
                'params': {'isolate_vocals': True}
            },
            {
                'name': 'Teste 7: Combinado (ruído + mono + filtro)',
                'params': {
                    'remove_noise': True,
                    'convert_to_mono': True,
                    'apply_highpass_filter': True
                }
            }
        ]
        
        results = []
        
        for test in tests:
            result = self.upload_file_and_test(
                audio_file_path,
                test['name'],
                **test['params']
            )
            results.append({
                'test': test['name'],
                'success': result is not None and result.get('status') == 'completed',
                'job_id': result.get('id') if result else None
            })
            
            time.sleep(1)  # Pausa entre testes
        
        # Relatório final
        print("\n" + "=" * 60)
        print("📊 RELATÓRIO FINAL DOS TESTES")
        print("=" * 60)
        
        successful = 0
        for result in results:
            status = "✅ PASSOU" if result['success'] else "❌ FALHOU"
            print(f"{status} | {result['test']}")
            if result['success']:
                successful += 1
        
        print(f"\n🏆 Resultados: {successful}/{len(results)} testes passaram")
        
        if successful == len(results):
            print("🎉 Todos os testes passaram! Serviço funcionando perfeitamente.")
        else:
            print(f"⚠️  {len(results) - successful} testes falharam. Verifique os logs.")


def main():
    """Função principal"""
    print("🎵 Audio Normalization Service - Script de Teste")
    
    # Verifica se arquivo de teste foi fornecido
    if len(sys.argv) < 2:
        # Procura arquivo padrão
        default_file = "C:/Users/johnfreitas/Desktop/YTCaption-Easy-Youtube-API/services/video-downloader/cache/09839DpTctU_audio_Eagles - Hotel California (Live 1977) (Official Video) [HD].webm"
        
        if os.path.exists(default_file):
            audio_file = default_file
            print(f"📁 Usando arquivo padrão: {audio_file}")
        else:
            print("❌ Arquivo de áudio não fornecido!")
            print("Uso: python test_normalization.py <caminho_para_arquivo_audio>")
            print("Ou coloque um arquivo de teste no diretório atual")
            return
    else:
        audio_file = sys.argv[1]
    
    # Verifica se arquivo existe
    if not os.path.exists(audio_file):
        print(f"❌ Arquivo não encontrado: {audio_file}")
        return
    
    # Executa testes
    tester = AudioNormalizationTester()
    tester.run_all_tests(audio_file)


if __name__ == "__main__":
    main()