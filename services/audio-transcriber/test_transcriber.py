#!/usr/bin/env python3
"""
Test script para o Audio Transcriber Service
Executa testes abrangentes das funcionalidades de transcrição
"""

import requests
import json
import time
import os
from pathlib import Path
import tempfile
import wave
import numpy as np

# Configuração do serviço
BASE_URL = "http://localhost:8001"
TEST_TIMEOUT = 120  # 2 minutos para transcrição


def create_test_audio(filename: str, duration: int = 5, sample_rate: int = 16000):
    """Cria arquivo de áudio de teste"""
    # Gera um tom simples
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Tom de 440Hz (A4)
    wave_data = np.sin(2 * np.pi * 440 * t)
    
    # Normaliza para 16-bit
    wave_data = (wave_data * 32767).astype(np.int16)
    
    # Salva como WAV
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())
    
    return filename


def print_header(title: str):
    """Imprime cabeçalho de seção"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_result(test_name: str, success: bool, details: str = ""):
    """Imprime resultado do teste"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     → {details}")


def wait_for_service():
    """Aguarda o serviço ficar disponível"""
    print("🔍 Verificando se o serviço está disponível...")
    for i in range(30):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Serviço disponível!")
                return True
        except requests.exceptions.RequestException:
            if i == 0:
                print("⏳ Aguardando serviço inicializar...")
            time.sleep(2)
    
    print("❌ Serviço não está disponível")
    return False


def test_health_check():
    """Testa endpoint de health check"""
    print_header("TESTE 1: Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        success = response.status_code == 200
        
        if success:
            data = response.json()
            details = f"Status: {data.get('status')}, Service: {data.get('service')}"
        else:
            details = f"Status code: {response.status_code}"
            
        print_result("Health Check", success, details)
        return success
        
    except Exception as e:
        print_result("Health Check", False, f"Erro: {e}")
        return False


def test_transcription_job():
    """Testa criação e processamento de job de transcrição"""
    print_header("TESTE 2: Job de Transcrição")
    
    try:
        # Cria arquivo de teste
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file = create_test_audio(tmp.name, duration=3)
        
        try:
            # Cria job de transcrição
            with open(audio_file, 'rb') as f:
                files = {'file': ('test_audio.wav', f, 'audio/wav')}
                response = requests.post(f"{BASE_URL}/jobs", files=files)
            
            if response.status_code != 200:
                print_result("Criar Job", False, f"Status: {response.status_code}")
                return False
            
            job_data = response.json()
            job_id = job_data['id']
            
            print_result("Criar Job", True, f"Job ID: {job_id}")
            
            # Aguarda processamento
            print("⏳ Aguardando transcrição...")
            for i in range(TEST_TIMEOUT):
                response = requests.get(f"{BASE_URL}/jobs/{job_id}")
                if response.status_code == 200:
                    job_status = response.json()
                    status = job_status['status']
                    progress = job_status.get('progress', 0)
                    
                    if status == 'completed':
                        print_result("Transcrição Completa", True, f"Progress: {progress}%")
                        
                        # Testa download do arquivo
                        response = requests.get(f"{BASE_URL}/jobs/{job_id}/download")
                        download_success = response.status_code == 200
                        print_result("Download SRT", download_success, 
                                   f"Size: {len(response.content)} bytes" if download_success else "Falhou")
                        
                        # Testa obter texto
                        response = requests.get(f"{BASE_URL}/jobs/{job_id}/text")
                        text_success = response.status_code == 200
                        if text_success:
                            text_data = response.json()
                            text_preview = text_data.get('text', '')[:50] + "..." if len(text_data.get('text', '')) > 50 else text_data.get('text', '')
                            print_result("Obter Texto", True, f"Text: '{text_preview}'")
                        else:
                            print_result("Obter Texto", False, f"Status: {response.status_code}")
                        
                        return True
                    elif status == 'failed':
                        error_msg = job_status.get('error_message', 'Erro desconhecido')
                        print_result("Transcrição", False, f"Erro: {error_msg}")
                        return False
                    elif i % 10 == 0:  # Log a cada 10 segundos
                        print(f"   Status: {status}, Progress: {progress}%")
                else:
                    print_result("Consultar Status", False, f"Status: {response.status_code}")
                    return False
                
                time.sleep(1)
            
            print_result("Transcrição", False, "Timeout aguardando processamento")
            return False
            
        finally:
            # Limpa arquivo temporário
            if os.path.exists(audio_file):
                os.unlink(audio_file)
                
    except Exception as e:
        print_result("Job de Transcrição", False, f"Erro: {e}")
        return False


def test_invalid_file():
    """Testa upload de arquivo inválido"""
    print_header("TESTE 3: Arquivo Inválido")
    
    try:
        # Cria arquivo de texto como "áudio"
        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False) as f:
            f.write("Este não é um arquivo de áudio")
            invalid_file = f.name
        
        try:
            with open(invalid_file, 'rb') as f:
                files = {'file': ('fake_audio.txt', f, 'text/plain')}
                response = requests.post(f"{BASE_URL}/jobs", files=files)
            
            # Deve rejeitar arquivo inválido
            success = response.status_code in [400, 422]
            details = f"Status: {response.status_code}"
            if not success and response.status_code == 200:
                details += " (Deveria rejeitar arquivo inválido)"
            
            print_result("Rejeitar Arquivo Inválido", success, details)
            return success
            
        finally:
            if os.path.exists(invalid_file):
                os.unlink(invalid_file)
                
    except Exception as e:
        print_result("Arquivo Inválido", False, f"Erro: {e}")
        return False


def test_large_file():
    """Testa arquivo muito grande"""
    print_header("TESTE 4: Arquivo Muito Grande")
    
    try:
        # Cria arquivo maior que o limite
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            # Arquivo de 30 segundos (maior que normal)
            audio_file = create_test_audio(tmp.name, duration=30)
        
        try:
            with open(audio_file, 'rb') as f:
                files = {'file': ('large_audio.wav', f, 'audio/wav')}
                response = requests.post(f"{BASE_URL}/jobs", files=files)
            
            # Pode aceitar ou rejeitar dependendo da configuração
            if response.status_code == 200:
                print_result("Aceitar Arquivo Grande", True, "Arquivo aceito")
                return True
            elif response.status_code in [400, 413, 422]:
                print_result("Rejeitar Arquivo Grande", True, f"Rejeitado: {response.status_code}")
                return True
            else:
                print_result("Arquivo Grande", False, f"Status inesperado: {response.status_code}")
                return False
                
        finally:
            if os.path.exists(audio_file):
                os.unlink(audio_file)
                
    except Exception as e:
        print_result("Arquivo Grande", False, f"Erro: {e}")
        return False


def test_duplicate_job():
    """Testa job duplicado (mesmo arquivo)"""
    print_header("TESTE 5: Job Duplicado")
    
    try:
        # Cria arquivo de teste
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file = create_test_audio(tmp.name, duration=2)
        
        try:
            # Primeiro job
            with open(audio_file, 'rb') as f:
                files = {'file': ('duplicate_test.wav', f, 'audio/wav')}
                response1 = requests.post(f"{BASE_URL}/jobs", files=files)
            
            if response1.status_code != 200:
                print_result("Primeiro Job", False, f"Status: {response1.status_code}")
                return False
            
            job1_id = response1.json()['id']
            print_result("Primeiro Job", True, f"Job ID: {job1_id}")
            
            # Segundo job (mesmo arquivo)
            with open(audio_file, 'rb') as f:
                files = {'file': ('duplicate_test.wav', f, 'audio/wav')}
                response2 = requests.post(f"{BASE_URL}/jobs", files=files)
            
            if response2.status_code != 200:
                print_result("Segundo Job", False, f"Status: {response2.status_code}")
                return False
            
            job2_id = response2.json()['id']
            
            # Deve retornar o mesmo job ID ou um novo
            if job1_id == job2_id:
                print_result("Job Duplicado", True, "Mesmo job retornado")
            else:
                print_result("Job Duplicado", True, f"Novo job: {job2_id}")
            
            return True
            
        finally:
            if os.path.exists(audio_file):
                os.unlink(audio_file)
                
    except Exception as e:
        print_result("Job Duplicado", False, f"Erro: {e}")
        return False


def test_job_listing():
    """Testa listagem de jobs"""
    print_header("TESTE 6: Listagem de Jobs")
    
    try:
        response = requests.get(f"{BASE_URL}/jobs")
        success = response.status_code == 200
        
        if success:
            jobs = response.json()
            details = f"Total de jobs: {len(jobs)}"
            if jobs:
                details += f", Primeiro job: {jobs[0].get('id', 'N/A')}"
        else:
            details = f"Status: {response.status_code}"
        
        print_result("Listar Jobs", success, details)
        return success
        
    except Exception as e:
        print_result("Listagem de Jobs", False, f"Erro: {e}")
        return False


def test_admin_endpoints():
    """Testa endpoints administrativos"""
    print_header("TESTE 7: Endpoints Admin")
    
    tests_passed = 0
    total_tests = 2
    
    try:
        # Testa estatísticas
        response = requests.get(f"{BASE_URL}/admin/stats")
        success = response.status_code == 200
        if success:
            stats = response.json()
            details = f"Stats obtidas: {len(stats)} campos"
        else:
            details = f"Status: {response.status_code}"
        
        print_result("Estatísticas Admin", success, details)
        if success:
            tests_passed += 1
        
        # Testa limpeza manual
        response = requests.post(f"{BASE_URL}/admin/cleanup")
        success = response.status_code == 200
        if success:
            cleanup_data = response.json()
            details = f"Limpeza: {cleanup_data.get('message', 'OK')}"
        else:
            details = f"Status: {response.status_code}"
        
        print_result("Limpeza Manual", success, details)
        if success:
            tests_passed += 1
        
        return tests_passed == total_tests
        
    except Exception as e:
        print_result("Endpoints Admin", False, f"Erro: {e}")
        return False


def main():
    """Executa todos os testes"""
    print_header("AUDIO TRANSCRIBER SERVICE - TESTE COMPLETO")
    print(f"🎯 Testando serviço em: {BASE_URL}")
    
    if not wait_for_service():
        print("\n❌ Não foi possível conectar ao serviço. Verifique se está rodando.")
        return
    
    # Lista de testes
    tests = [
        ("Health Check", test_health_check),
        ("Job de Transcrição", test_transcription_job),
        ("Arquivo Inválido", test_invalid_file),
        ("Arquivo Grande", test_large_file),
        ("Job Duplicado", test_duplicate_job),
        ("Listagem de Jobs", test_job_listing),
        ("Endpoints Admin", test_admin_endpoints),
    ]
    
    # Executa testes
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Erro crítico no teste '{test_name}': {e}")
            results.append((test_name, False))
    
    # Sumário final
    print_header("RESUMO DOS TESTES")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print(f"\n📊 RESULTADO FINAL: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! O serviço está funcionando corretamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique os logs do serviço.")
        
    # Instruções
    print_header("COMO USAR")
    print("1. Para criar job de transcrição:")
    print(f"   curl -X POST -F 'file=@audio.wav' {BASE_URL}/jobs")
    print("\n2. Para consultar status:")
    print(f"   curl {BASE_URL}/jobs/{{job_id}}")
    print("\n3. Para baixar transcrição:")
    print(f"   curl {BASE_URL}/jobs/{{job_id}}/download")


if __name__ == "__main__":
    main()