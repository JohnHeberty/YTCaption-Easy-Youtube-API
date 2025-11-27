#!/usr/bin/env python3
"""
Teste de Clonagem de Voz com F5-TTS
Compara qualidade entre XTTS e F5-TTS
"""
import requests
import time
from pathlib import Path

# Configuração
API_URL = "http://localhost:8005"
TEST_AUDIO = "/home/john/YTCaption-Easy-Youtube-API/services/audio-voice/tests/Teste.ogg"

# Texto para teste de dublagem (português PT-BR)
TEST_TEXT = """
Olá, este é um teste de clonagem de voz usando F5-TTS, o motor de máxima qualidade e expressividade.
O F5-TTS utiliza Flow Matching Diffusion para gerar vozes extremamente naturais e expressivas.
Vamos comparar a qualidade com o resultado anterior do XTTS.
"""

def check_audio_file():
    """Verifica se o arquivo de áudio existe"""
    audio_path = Path(TEST_AUDIO)
    if not audio_path.exists():
        print(f"❌ Arquivo não encontrado: {TEST_AUDIO}")
        return False
    print(f"✅ Arquivo encontrado: {TEST_AUDIO} ({audio_path.stat().st_size / 1024:.1f} KB)")
    return True

def clone_voice_f5tts():
    """Clona a voz usando F5-TTS"""
    print("\n" + "="*80)
    print("🎤 CLONAGEM DE VOZ COM F5-TTS (MÁXIMA QUALIDADE)")
    print("="*80)
    
    # Transcrição do áudio de referência para F5-TTS
    ref_text = "Olá, como vai? Tudo bem?"  # Ajuste conforme o conteúdo real do Teste.ogg
    
    # Preparar arquivo
    with open(TEST_AUDIO, 'rb') as f:
        files = {'file': ('Teste.ogg', f, 'audio/ogg')}
        
        # Dados do formulário
        data = {
            'name': 'Voz Teste F5-TTS High Quality',
            'language': 'pt-BR',
            'description': 'Clonagem com F5-TTS para máxima qualidade e expressividade',
            'tts_engine': 'f5tts',  # Motor F5-TTS
            'ref_text': ref_text  # F5-TTS PRECISA de ref_text
        }
        
        print(f"\n📤 Enviando para F5-TTS...")
        print(f"   Nome: {data['name']}")
        print(f"   Engine: {data['tts_engine']}")
        print(f"   Ref Text: {data['ref_text']}")
        
        response = requests.post(
            f"{API_URL}/voices/clone",
            files=files,
            data=data
        )
    
    if response.status_code != 202:
        print(f"❌ Erro: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    job_id = result.get('job_id')
    print(f"✅ Job criado: {job_id}")
    
    return job_id

def wait_for_job(job_id):
    """Aguarda conclusão do job"""
    print(f"\n⏳ Processando job {job_id}...")
    
    max_attempts = 120  # 10 minutos (F5-TTS é mais lento)
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
            bar_length = 30
            filled = int(bar_length * progress / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r   [{bar}] {progress}% - {status}", end='', flush=True)
            time.sleep(5)
    
    print(f"\n⏱️  Timeout")
    return None

def generate_dubbing_f5tts(voice_id):
    """Gera dublagem com F5-TTS"""
    print("\n" + "="*80)
    print("🎬 DUBLAGEM COM F5-TTS")
    print("="*80)
    
    data = {
        "text": TEST_TEXT,
        "source_language": "pt-BR",
        "mode": "dubbing_with_clone",
        "quality_profile": "expressive",  # Máxima expressividade
        "voice_id": voice_id,
        "tts_engine": "f5tts",  # Usar F5-TTS
        "enable_rvc": False,
    }
    
    print(f"\n📝 Texto: {TEST_TEXT[:80]}...")
    print(f"🎤 Voice ID: {voice_id}")
    print(f"⚡ Engine: F5-TTS")
    print(f"🎯 Quality: expressive")
    
    response = requests.post(f"{API_URL}/jobs", data=data)
    
    if response.status_code != 200:
        print(f"❌ Erro: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    job_id = result.get('id')
    print(f"\n✅ Job criado: {job_id}")
    
    return job_id

def download_audio(job_id, output_path="output_f5tts.wav"):
    """Baixa o áudio gerado"""
    print(f"\n📥 Baixando áudio...")
    
    response = requests.get(
        f"{API_URL}/jobs/{job_id}/download",
        params={'format': 'wav'}
    )
    
    if response.status_code != 200:
        print(f"❌ Erro ao baixar: {response.status_code}")
        return False
    
    output = Path(output_path)
    with open(output, 'wb') as f:
        f.write(response.content)
    
    size_kb = output.stat().st_size / 1024
    print(f"✅ Salvo: {output} ({size_kb:.1f} KB)")
    
    return True

def main():
    """Teste completo com F5-TTS"""
    print("\n" + "="*80)
    print("🎯 TESTE DE CLONAGEM COM F5-TTS (MÁXIMA QUALIDADE)")
    print("="*80)
    
    # 1. Verificar arquivo
    if not check_audio_file():
        return
    
    # 2. Clonar voz com F5-TTS
    clone_job_id = clone_voice_f5tts()
    if not clone_job_id:
        return
    
    # 3. Aguardar clonagem
    clone_result = wait_for_job(clone_job_id)
    if not clone_result:
        return
    
    voice_id = clone_result.get('voice_id')
    if not voice_id:
        print("❌ Voice ID não retornado")
        return
    
    print(f"\n✅ Voz clonada com F5-TTS!")
    print(f"   Voice ID: {voice_id}")
    print(f"   Nome: {clone_result.get('voice_name')}")
    
    # 4. Gerar dublagem com F5-TTS
    dub_job_id = generate_dubbing_f5tts(voice_id)
    if not dub_job_id:
        return
    
    # 5. Aguardar dublagem
    dub_result = wait_for_job(dub_job_id)
    if not dub_result:
        return
    
    print(f"\n✅ Dublagem gerada!")
    print(f"   Duração: {dub_result.get('duration', 0):.2f}s")
    
    # 6. Baixar áudio
    if download_audio(dub_job_id, "output_f5tts_high_quality.wav"):
        print("\n" + "="*80)
        print("🎉 TESTE F5-TTS CONCLUÍDO!")
        print("="*80)
        print(f"\n📊 Comparação:")
        print(f"   🔵 XTTS: output_high_fidelity.wav")
        print(f"   🟢 F5-TTS: output_f5tts_high_quality.wav")
        print(f"\n🎧 Ouvir F5-TTS:")
        print(f"   ffplay output_f5tts_high_quality.wav")
        print(f"\n💡 F5-TTS deve ter:")
        print(f"   ✅ Maior naturalidade")
        print(f"   ✅ Melhor expressividade")
        print(f"   ✅ Entonação mais humana")
        print(f"   ⚠️  Processamento mais lento (2-4x)")
        print("="*80)

if __name__ == "__main__":
    main()
