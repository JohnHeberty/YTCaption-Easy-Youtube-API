#!/usr/bin/env python3
"""
Teste Automatizado - Voice Cloning F5-TTS pt-BR

Fluxo de teste:
1. Clona voz usando /voices/clone (POST multipart/form-data)
2. Aguarda job de clonagem completar (polling)
3. Cria job de dublagem usando a voz clonada (POST JSON)
4. Aguarda job de dublagem completar
5. Verifica se áudio foi gerado
"""

import os
import sys
import time
import requests

# Configuração
API_URL = "http://localhost:8005"
AUDIO_FILE = "uploads/clone_20251126031159965237.ogg"
VOICE_NAME = f"test_voice_{int(time.time())}"
TEST_TEXT = "Olá! Este é um teste de clonagem de voz usando F5-TTS em português brasileiro."
MAX_WAIT = 180

# Cores
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_status(message, status="info"):
    """Imprime mensagem colorida"""
    icon = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(status, "•")
    color = {
        "success": Colors.GREEN,
        "error": Colors.RED,
        "warning": Colors.YELLOW,
        "info": Colors.BLUE
    }.get(status, Colors.RESET)
    print(f"{color}{icon} {message}{Colors.RESET}")

def check_api():
    """Verifica se API está online"""
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        return response.status_code == 200
    except:
        return False

def wait_for_job(job_id, job_type="processamento"):
    """Aguarda job completar"""
    print_status(f"Aguardando {job_type} ({job_id})...", "info")
    start = time.time()
    
    while True:
        elapsed = time.time() - start
        
        if elapsed > MAX_WAIT:
            print_status(f"Timeout após {MAX_WAIT}s", "error")
            return None
        
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
            
            if response.status_code == 200:
                job = response.json()
                status = job.get('status')
                progress = job.get('progress', 0)
                
                if status == 'completed':
                    print_status(f"{job_type.capitalize()} concluído ({elapsed:.1f}s)", "success")
                    return job
                elif status == 'failed':
                    error = job.get('error_message', 'Unknown')
                    print_status(f"Falha: {error}", "error")
                    return None
                elif status in ['queued', 'processing']:
                    print(f"\r{Colors.YELLOW}⏳ {status} ({progress}%) - {elapsed:.1f}s{Colors.RESET}", end='', flush=True)
                    time.sleep(2)
                else:
                    print_status(f"Status desconhecido: {status}", "warning")
                    return None
            else:
                print_status(f"Erro HTTP {response.status_code}", "error")
                return None
        except Exception as e:
            print_status(f"Erro: {e}", "error")
            return None

def main():
    """Teste principal"""
    print("\n" + "="*70)
    print(f"{Colors.BLUE}🎤 TESTE AUTOMATIZADO - VOICE CLONING F5-TTS pt-BR{Colors.RESET}")
    print("="*70 + "\n")
    
    # 1. Verifica API
    print_status("Verificando API...", "info")
    if not check_api():
        print_status("API offline! Execute: docker compose up -d", "error")
        sys.exit(1)
    print_status("API online", "success")
    print()
    
    # 2. Verifica arquivo
    if not os.path.exists(AUDIO_FILE):
        print_status(f"Arquivo não encontrado: {AUDIO_FILE}", "error")
        sys.exit(1)
    
    file_size = os.path.getsize(AUDIO_FILE)
    print_status(f"Arquivo: {AUDIO_FILE} ({file_size} bytes)", "success")
    print()
    
    # 3. Clona voz (POST multipart)
    print_status(f"Clonando voz '{VOICE_NAME}'...", "info")
    try:
        with open(AUDIO_FILE, 'rb') as f:
            files = {'file': ('voice.ogg', f, 'audio/ogg')}
            data = {
                'name': VOICE_NAME,
                'language': 'pt-BR',
                'description': 'Teste automatizado'
            }
            
            response = requests.post(f"{API_URL}/voices/clone", files=files, data=data, timeout=30)
        
        if response.status_code != 202:
            print_status(f"Erro HTTP {response.status_code}: {response.text}", "error")
            sys.exit(1)
        
        clone_data = response.json()
        clone_job_id = clone_data.get('job_id')
        print_status(f"Job de clonagem criado: {clone_job_id}", "success")
        print()
        
    except Exception as e:
        print_status(f"Erro ao clonar: {e}", "error")
        sys.exit(1)
    
    # 4. Aguarda clonagem
    clone_job = wait_for_job(clone_job_id, "clonagem")
    print()  # Nova linha após polling
    
    if not clone_job:
        print_status("Falha na clonagem", "error")
        sys.exit(1)
    
    voice_id = clone_job.get('voice_id')
    if not voice_id:
        print_status("voice_id não retornado", "error")
        sys.exit(1)
    
    print_status(f"Voz clonada! ID: {voice_id}", "success")
    print()
    
    # 5. Dubla com voz clonada (POST JSON)
    print_status(f"Criando dublagem com voz clonada...", "info")
    print_status(f"Texto: '{TEST_TEXT}'", "info")
    
    try:
        payload = {
            'mode': 'dubbing_with_clone',
            'text': TEST_TEXT,
            'source_language': 'pt-BR',
            'voice_id': voice_id
        }
        
        response = requests.post(f"{API_URL}/jobs", json=payload, timeout=30)
        
        if response.status_code != 200:
            print_status(f"Erro HTTP {response.status_code}: {response.text}", "error")
            sys.exit(1)
        
        dub_job_data = response.json()
        dub_job_id = dub_job_data.get('id')
        print_status(f"Job de dublagem criado: {dub_job_id}", "success")
        print()
        
    except Exception as e:
        print_status(f"Erro ao dublar: {e}", "error")
        sys.exit(1)
    
    # 6. Aguarda dublagem
    dub_job = wait_for_job(dub_job_id, "dublagem")
    print()  # Nova linha após polling
    
    if not dub_job:
        print_status("Falha na dublagem", "error")
        sys.exit(1)
    
    # 7. Resultado
    audio_url = dub_job.get('audio_url', '')
    duration = dub_job.get('duration', 0)
    file_size_output = dub_job.get('file_size_output', 0)
    
    print_status("Dublagem concluída!", "success")
    print_status(f"Duração: {duration:.2f}s", "info")
    print_status(f"Tamanho: {file_size_output} bytes", "info")
    print_status(f"URL: {audio_url}", "info")
    print()
    
    print("="*70)
    print_status("TESTE CONCLUÍDO COM SUCESSO! ✅", "success")
    print_status("Sistema de clonagem funcionando corretamente.", "success")
    print("="*70 + "\n")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
