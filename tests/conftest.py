"""
Configurações e fixtures pytest para testes do Audio Normalization Service
"""
import pytest
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any
import requests
import time
from datetime import datetime

# Configuração base
BASE_URL = "http://localhost:8001"
TEST_AUDIO_FILE = r"C:\Users\johnfreitas\Desktop\YTCaption-Easy-Youtube-API\services\video-downloader\cache\09839DpTctU_audio_Eagles - Hotel California (Live 1977) (Official Video) [HD].webm"
OUTPUT_DIR = Path(__file__).parent / "output"

# Timeouts e configurações
JOB_TIMEOUT = 900  # 15 minutos (temporário para debug)
POLL_INTERVAL = 5  # 5 segundos
MAX_RETRIES = 3

@pytest.fixture(scope="session")
def output_dir():
    """Fixture que garante que o diretório de output existe"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR

@pytest.fixture(scope="session")
def test_audio_file():
    """Fixture que valida e retorna o arquivo de teste"""
    if not os.path.exists(TEST_AUDIO_FILE):
        pytest.fail(f"Arquivo de teste não encontrado: {TEST_AUDIO_FILE}")
    return TEST_AUDIO_FILE

@pytest.fixture
def api_client():
    """Fixture que fornece cliente HTTP configurado"""
    session = requests.Session()
    session.timeout = 30
    return session

@pytest.fixture
def job_manager(api_client, output_dir):
    """Fixture que gerencia jobs de teste"""
    class JobManager:
        def __init__(self, client, output_dir):
            self.client = client
            self.output_dir = output_dir
            self.created_jobs = []
            
        def create_job(self, audio_file: str, **params) -> Dict[str, Any]:
            """Cria um job de processamento"""
            # Gera nome de arquivo único baseado no timestamp e parâmetros
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            param_hash = hash(str(sorted(params.items())))
            unique_filename = f"test_audio_{timestamp}_{abs(param_hash)}.webm"
            
            with open(audio_file, 'rb') as f:
                files = {'file': (unique_filename, f, 'audio/webm')}
                data = {
                    'apply_highpass_filter': str(params.get('apply_highpass_filter', False)).lower(),
                    'remove_noise': str(params.get('remove_noise', False)).lower(),
                    'isolate_vocals': str(params.get('isolate_vocals', False)).lower(),
                    'convert_to_mono': str(params.get('convert_to_mono', False)).lower(),
                    'set_sample_rate_16k': str(params.get('set_sample_rate_16k', False)).lower()
                }
                
                response = self.client.post(f"{BASE_URL}/jobs", files=files, data=data)
                response.raise_for_status()
                
                job_data = response.json()
                self.created_jobs.append(job_data['id'])
                return job_data
                
        def wait_for_completion(self, job_id: str) -> Dict[str, Any]:
            """Aguarda conclusão do job com timeout"""
            start_time = time.time()
            
            while time.time() - start_time < JOB_TIMEOUT:
                response = self.client.get(f"{BASE_URL}/jobs/{job_id}")
                response.raise_for_status()
                
                job_data = response.json()
                status = job_data.get('status')
                
                if status == 'completed':
                    # Verifica se tem output_file
                    if not job_data.get('output_file'):
                        raise Exception(f"Job {job_id} completed but has no output_file")
                    return job_data
                elif status == 'failed':
                    raise Exception(f"Job failed: {job_data.get('error_message', 'Unknown error')}")
                    
                time.sleep(POLL_INTERVAL)
                
            raise TimeoutError(f"Job {job_id} não completou em {JOB_TIMEOUT}s")
            
        def download_result(self, job_id: str, filename: str = None) -> Path:
            """Baixa resultado do job para pasta output"""
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"result_{job_id}_{timestamp}.webm"
                
            output_path = self.output_dir / filename
            
            # Primeiro pega os dados do job para obter o output_file
            job_response = self.client.get(f"{BASE_URL}/jobs/{job_id}")
            job_response.raise_for_status()
            job_data = job_response.json()
            
            if not job_data.get('output_file'):
                raise Exception(f"Job {job_id} has no output file. Status: {job_data.get('status')}, Error: {job_data.get('error_message')}")
            
            if job_data.get('status') != 'completed':
                raise Exception(f"Job {job_id} is not completed. Status: {job_data.get('status')}")
            
            # Baixa o arquivo usando o endpoint de download
            try:
                response = self.client.get(f"{BASE_URL}/jobs/{job_id}/download")
                response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                    
                # Verifica se o arquivo foi criado e tem conteúdo
                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise Exception(f"Downloaded file is empty or not created: {output_path}")
                    
                return output_path
                
            except Exception as e:
                # Se o download falhar, tenta deletar arquivo parcial
                if output_path.exists():
                    output_path.unlink()
                raise Exception(f"Download failed for job {job_id}: {str(e)}")
            
        def cleanup(self):
            """Limpa jobs criados durante o teste"""
            for job_id in self.created_jobs:
                try:
                    self.client.delete(f"{BASE_URL}/jobs/{job_id}")
                except:
                    pass  # Ignora erros de cleanup
                    
    manager = JobManager(api_client, output_dir)
    yield manager
    manager.cleanup()

@pytest.fixture
def service_health_check(api_client):
    """Verifica se o serviço está funcionando antes dos testes"""
    try:
        response = api_client.get(f"{BASE_URL}/health")
        response.raise_for_status()
        health_data = response.json()
        if health_data.get('status') != 'healthy':
            pytest.fail(f"Serviço não está saudável: {health_data}")
    except Exception as e:
        pytest.fail(f"Serviço não está acessível: {e}")
    return True

# Parametrização para testes de features
AUDIO_PROCESSING_PARAMS = [
    {'apply_highpass_filter': True},
    {'remove_noise': True},
    {'isolate_vocals': True},
    {'convert_to_mono': True},
    {'set_sample_rate_16k': True},
    {
        'apply_highpass_filter': True,
        'remove_noise': True,
        'convert_to_mono': True
    }
]

# IDs para os parâmetros
AUDIO_PROCESSING_IDS = [
    "highpass_filter",
    "noise_removal", 
    "vocal_isolation",
    "mono_conversion",
    "sample_rate_16k",
    "combined_processing"
]