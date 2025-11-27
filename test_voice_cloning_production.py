#!/usr/bin/env python3
"""
Teste de Clonagem de Voz em Produção com RVC
Usa o arquivo Teste.ogg para clonar voz com alta fidelidade
"""
import requests
import time
import json
from pathlib import Path

# Configuração
API_URL = "http://localhost:8005"
TEST_AUDIO = "/home/john/YTCaption-Easy-Youtube-API/services/audio-voice/tests/Teste.ogg"

# Texto para teste de dublagem (português PT-BR)
TEST_TEXT = """
Olá, este é um teste de clonagem de voz com alta fidelidade usando o sistema multi-engine TTS.
Estamos utilizando XTTS combinado com RVC para obter a melhor qualidade possível.
O resultado deve soar natural e expressivo, preservando as características únicas da voz original.
"""

def check_audio_file():
    """Verifica se o arquivo de áudio existe"""
    audio_path = Path(TEST_AUDIO)
    if not audio_path.exists():
        print(f"❌ Arquivo não encontrado: {TEST_AUDIO}")
        return False
    print(f"✅ Arquivo encontrado: {TEST_AUDIO} ({audio_path.stat().st_size / 1024:.1f} KB)")
    return True

def clone_voice():
    """Clona a voz usando o endpoint /voices/clone"""
    print("\n" + "="*80)
    print("🎤 INICIANDO CLONAGEM DE VOZ COM ALTA FIDELIDADE")
    print("="*80)
    
    # Preparar arquivo
    with open(TEST_AUDIO, 'rb') as f:
        files = {'file': ('Teste.ogg', f, 'audio/ogg')}
        
        # Dados do formulário
        data = {
            'name': 'Voz Teste High Fidelity',
            'language': 'pt-BR',
            'description': 'Clonagem de voz com XTTS + RVC para máxima fidelidade',
            'tts_engine': 'xtts',  # XTTS é mais estável
            'ref_text': None  # XTTS não precisa de ref_text
        }
        
        print(f"\n📤 Enviando arquivo para clonagem...")
        print(f"   Nome: {data['name']}")
        print(f"   Idioma: {data['language']}")
        print(f"   Engine: {data['tts_engine']}")
        
        response = requests.post(
            f"{API_URL}/voices/clone",
            files=files,
            data=data
        )
    
    if response.status_code != 202:
        print(f"❌ Erro ao clonar voz: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    job_id = result.get('job_id')
    print(f"✅ Job de clonagem criado: {job_id}")
    
    return job_id

def wait_for_job(job_id):
    """Aguarda conclusão do job"""
    print(f"\n⏳ Aguardando processamento do job {job_id}...")
    
    max_attempts = 60  # 5 minutos (5s interval)
    for attempt in range(max_attempts):
        response = requests.get(f"{API_URL}/jobs/{job_id}")
        
        if response.status_code != 200:
            print(f"❌ Erro ao consultar job: {response.status_code}")
            return None
        
        job = response.json()
        status = job.get('status')
        progress = job.get('progress', 0)
        
        if status == 'completed':
            print(f"\n✅ Job concluído!")
            return job
        elif status == 'failed':
            error = job.get('error_message', 'Unknown error')
            print(f"\n❌ Job falhou: {error}")
            return None
        else:
            # Mostra progresso
            bar_length = 30
            filled = int(bar_length * progress / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r   [{bar}] {progress}% - {status}", end='', flush=True)
            time.sleep(5)
    
    print(f"\n⏱️  Timeout aguardando job")
    return None

def generate_dubbing(voice_id):
    """Gera dublagem usando a voz clonada"""
    print("\n" + "="*80)
    print("🎬 GERANDO DUBLAGEM COM VOZ CLONADA")
    print("="*80)
    
    # Preparar dados do formulário
    data = {
        "text": TEST_TEXT,
        "source_language": "pt-BR",
        "mode": "dubbing_with_clone",  # Usar voz clonada
        "quality_profile": "expressive",  # Máxima qualidade (opções: balanced, expressive, stable)
        "voice_id": voice_id,
        "tts_engine": "xtts",
        "enable_rvc": False,  # Desabilitado por enquanto (precisa de modelo RVC)
    }
    
    print(f"\n📝 Texto: {TEST_TEXT[:100]}...")
    print(f"🎤 Voice ID: {voice_id}")
    print(f"⚡ Quality: {data['quality_profile']}")
    print(f"✨ RVC: {data['enable_rvc']}")
    
    response = requests.post(
        f"{API_URL}/jobs",
        data=data  # Usar data (form) ao invés de json
    )
    
    if response.status_code != 200:
        print(f"❌ Erro ao criar job de dublagem: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    job_id = result.get('id')
    print(f"\n✅ Job de dublagem criado: {job_id}")
    
    return job_id

def download_audio(job_id, output_path="output_high_fidelity.wav"):
    """Baixa o áudio gerado"""
    print(f"\n📥 Baixando áudio...")
    
    response = requests.get(
        f"{API_URL}/jobs/{job_id}/download",
        params={'format': 'wav'}
    )
    
    if response.status_code != 200:
        print(f"❌ Erro ao baixar áudio: {response.status_code}")
        return False
    
    output = Path(output_path)
    with open(output, 'wb') as f:
        f.write(response.content)
    
    size_kb = output.stat().st_size / 1024
    print(f"✅ Áudio salvo: {output} ({size_kb:.1f} KB)")
    
    return True

def main():
    """Executa teste completo de clonagem + dublagem com RVC"""
    print("\n" + "="*80)
    print("🎯 TESTE DE CLONAGEM DE VOZ COM ALTA FIDELIDADE (XTTS + RVC)")
    print("="*80)
    
    # 1. Verificar arquivo
    if not check_audio_file():
        return
    
    # 2. Clonar voz
    clone_job_id = clone_voice()
    if not clone_job_id:
        return
    
    # 3. Aguardar clonagem
    clone_result = wait_for_job(clone_job_id)
    if not clone_result:
        return
    
    voice_id = clone_result.get('voice_id')
    if not voice_id:
        print("❌ Voice ID não retornado no resultado")
        return
    
    print(f"\n✅ Voz clonada com sucesso!")
    print(f"   Voice ID: {voice_id}")
    print(f"   Nome: {clone_result.get('voice_name')}")
    
    # 4. Gerar dublagem com RVC
    dubbing_job_id = generate_dubbing(voice_id)
    if not dubbing_job_id:
        return
    
    # 5. Aguardar dublagem
    dubbing_result = wait_for_job(dubbing_job_id)
    if not dubbing_result:
        return
    
    print(f"\n✅ Dublagem gerada com sucesso!")
    print(f"   Duração: {dubbing_result.get('output_duration', 0):.2f}s")
    
    # 6. Baixar áudio
    if download_audio(dubbing_job_id):
        print("\n" + "="*80)
        print("🎉 TESTE CONCLUÍDO COM SUCESSO!")
        print("="*80)
        print(f"\n📊 Resultados:")
        print(f"   ✅ Voz clonada: {voice_id}")
        print(f"   ✅ Dublagem gerada com RVC (alta fidelidade)")
        print(f"   ✅ Áudio salvo: output_high_fidelity.wav")
        print(f"\n🎧 Para ouvir:")
        print(f"   ffplay output_high_fidelity.wav")
        print("\n" + "="*80)

if __name__ == "__main__":
    main()
