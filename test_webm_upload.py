#!/usr/bin/env python3
"""
Script para testar o upload de arquivos .webm (e outros formatos) 
para reproduzir o bug "Formato de áudio não reconhecido"
"""

import requests
import json
import tempfile
import os
from pathlib import Path

# Configuração
API_URL = "http://localhost:8001"

def create_test_audio():
    """Cria um arquivo de áudio de teste usando ffmpeg"""
    test_file = Path("test_audio.wav")
    if not test_file.exists():
        print("Criando arquivo de teste WAV...")
        os.system('ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -ar 44100 test_audio.wav')
    return test_file

def create_test_webm_audio():
    """Cria um arquivo .webm de áudio de teste"""
    test_file = Path("test_audio.webm")
    if not test_file.exists():
        print("Criando arquivo de teste WEBM (áudio)...")
        os.system('ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -c:a libvorbis test_audio.webm')
    return test_file

def create_test_webm_video():
    """Cria um arquivo .webm de vídeo com áudio de teste"""
    test_file = Path("test_video.webm")
    if not test_file.exists():
        print("Criando arquivo de teste WEBM (vídeo com áudio)...")
        os.system('ffmpeg -f lavfi -i "testsrc=duration=2:size=320x240:rate=30" -f lavfi -i "sine=frequency=440:duration=2" -c:v libvpx -c:a libvorbis test_video.webm')
    return test_file

def test_upload(file_path, mime_type=None):
    """Testa o upload de um arquivo"""
    print(f"\n{'=' * 60}")
    print(f"TESTANDO: {file_path}")
    print(f"MIME TYPE: {mime_type}")
    print(f"{'=' * 60}")
    
    try:
        with open(file_path, 'rb') as f:
            files = {}
            if mime_type:
                files['file'] = (file_path.name, f, mime_type)
            else:
                files['file'] = (file_path.name, f)
            
            # Dados do formulário
            data = {
                'normalize': 'true',
                'remove_noise': 'false',
                'vocal_isolation': 'false',
                'output_format': 'webm'
            }
            
            response = requests.post(f"{API_URL}/normalize", files=files, data=data)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ SUCCESS - Job ID: {result.get('job_id')}")
                return result.get('job_id')
            else:
                print(f"❌ FAILED - {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return None

def check_job_status(job_id):
    """Verifica o status de um job"""
    if not job_id:
        return
        
    print(f"\n📊 Verificando status do job: {job_id}")
    try:
        response = requests.get(f"{API_URL}/status/{job_id}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

def main():
    print("🎵 TESTE DE UPLOAD DE ARQUIVOS WEBM")
    print("====================================")
    
    # Criar arquivos de teste
    wav_file = create_test_audio()
    webm_audio_file = create_test_webm_audio()
    webm_video_file = create_test_webm_video()
    
    # Teste 1: WAV normal (deve funcionar)
    print("\n🎵 TESTE 1: Upload de WAV")
    job1 = test_upload(wav_file, "audio/wav")
    
    # Teste 2: WEBM áudio com MIME correto (deve funcionar)
    print("\n🎵 TESTE 2: Upload de WEBM (áudio) com MIME audio/webm")
    job2 = test_upload(webm_audio_file, "audio/webm")
    
    # Teste 3: WEBM áudio com MIME de vídeo (reproduz o bug original)
    print("\n🎵 TESTE 3: Upload de WEBM (áudio) com MIME video/webm")
    job3 = test_upload(webm_audio_file, "video/webm")
    
    # Teste 4: WEBM vídeo com áudio com MIME de vídeo (deve extrair áudio)
    print("\n🎵 TESTE 4: Upload de WEBM (vídeo) com MIME video/webm")
    job4 = test_upload(webm_video_file, "video/webm")
    
    # Teste 5: Simular o comando curl exato do usuário
    print("\n🎵 TESTE 5: Simulando curl exato do usuário")
    print("curl -F 'file=@test_audio.webm;type=video/webm' ...")
    job5 = test_upload(webm_audio_file, "video/webm")
    
    print(f"\n{'=' * 60}")
    print("RESUMO DOS TESTES:")
    print(f"WAV (audio/wav): {'✅' if job1 else '❌'}")
    print(f"WEBM áudio (audio/webm): {'✅' if job2 else '❌'}")
    print(f"WEBM áudio (video/webm): {'✅' if job3 else '❌'}")
    print(f"WEBM vídeo (video/webm): {'✅' if job4 else '❌'}")
    print(f"Curl simulado: {'✅' if job5 else '❌'}")
    print(f"{'=' * 60}")
    
    # Verificar status dos jobs que funcionaram
    for job_id in [job1, job2, job3, job4, job5]:
        if job_id:
            check_job_status(job_id)

if __name__ == "__main__":
    main()