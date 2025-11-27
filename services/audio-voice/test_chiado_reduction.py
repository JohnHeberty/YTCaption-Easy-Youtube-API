#!/usr/bin/env python3
"""
Teste de Comparação: Redução de Chiado F5-TTS
Compara os 3 perfis F5-TTS padrão com o mesmo texto e voz
"""
import requests
import time
import json
import subprocess
from pathlib import Path

API_URL = "http://localhost:8005"
VOICE_AUDIO = "tests/Teste.ogg"

# Texto médio para teste (não muito curto, não muito longo)
TEST_TEXT = """
A inteligência artificial está transformando o mundo de maneiras incríveis.
Sistemas de síntese de voz agora conseguem reproduzir emoções e nuances com 
surpreendente naturalidade. Essa tecnologia permite criar audiolivros, podcasts 
e conteúdo multimídia de alta qualidade sem a necessidade de estúdios profissionais.
"""

def cleanup_old_voices():
    """Remove vozes antigas de testes"""
    try:
        resp = requests.get(f"{API_URL}/voices")
        if resp.status_code != 200:
            return
            
        voices = resp.json()
        if not isinstance(voices, list):
            return
        
        removed = 0
        for voice in voices:
            if isinstance(voice, dict) and voice.get('name', '').startswith('TestChiado'):
                requests.delete(f"{API_URL}/voices/{voice['id']}")
                removed += 1
        
        if removed > 0:
            print(f"🧹 Limpou {removed} vozes antigas")
    except Exception as e:
        print(f"⚠️ Erro ao limpar vozes: {e}")

def clone_voice(profile_name):
    """Clona voz com perfil específico"""
    print(f"\n🎤 Clonando voz para perfil: {profile_name}")
    
    # Upload e clone
    with open(VOICE_AUDIO, 'rb') as f:
        files = {'file': ('Teste.ogg', f, 'audio/ogg')}
        data = {
            'name': f'TestChiado_{profile_name}',
            'language': 'pt-BR',
            'tts_engine': 'f5tts',
            'description': f'Teste de chiado - perfil {profile_name}'
        }
        
        resp = requests.post(
            f"{API_URL}/voices/clone",
            files=files,
            data=data
        )
    
    if resp.status_code != 200:
        print(f"❌ Erro ao clonar: {resp.text}")
        return None
    
    job_data = resp.json()
    job_id = job_data['id']
    
    # Aguardar conclusão
    print(f"   Aguardando job {job_id}...")
    for _ in range(60):
        job_resp = requests.get(f"{API_URL}/jobs/{job_id}")
        job = job_resp.json()
        
        if job['status'] == 'completed':
            voice_id = job['result']['voice_id']
            print(f"✅ Voz clonada: {voice_id}")
            return voice_id
        elif job['status'] == 'failed':
            print(f"❌ Job falhou: {job.get('error', 'Erro desconhecido')}")
            return None
        
        time.sleep(2)
    
    print("❌ Timeout ao clonar voz")
    return None

def generate_audio(voice_id, profile_id, profile_name):
    """Gera áudio com perfil específico"""
    print(f"\n🔊 Gerando áudio com perfil: {profile_name}")
    
    data = {
        'mode': 'dubbing',
        'text': TEST_TEXT,
        'source_language': 'pt-BR',
        'voice_id': voice_id,
        'tts_engine': 'f5tts',
        'quality_profile_id': profile_id
    }
    
    resp = requests.post(f"{API_URL}/jobs", data=data)
    
    if resp.status_code != 200:
        print(f"❌ Erro ao criar job: {resp.text}")
        return None
    
    job_data = resp.json()
    job_id = job_data['id']
    
    # Aguardar conclusão
    print(f"   Aguardando job {job_id}...")
    for _ in range(180):
        job_resp = requests.get(f"{API_URL}/jobs/{job_id}")
        job = job_resp.json()
        
        if job['status'] == 'completed':
            print(f"✅ Áudio gerado!")
            return job_id
        elif job['status'] == 'failed':
            print(f"❌ Job falhou: {job.get('error', 'Erro desconhecido')}")
            return None
        
        time.sleep(2)
    
    print("❌ Timeout ao gerar áudio")
    return None

def download_audio(job_id, output_file):
    """Baixa áudio gerado"""
    resp = requests.get(f"{API_URL}/jobs/{job_id}/download?format=wav")
    
    if resp.status_code != 200:
        print(f"❌ Erro ao baixar áudio: {resp.status_code}")
        return False
    
    with open(output_file, 'wb') as f:
        f.write(resp.content)
    
    # Info do arquivo
    size_kb = len(resp.content) / 1024
    
    # Duração via ffprobe
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', output_file],
            capture_output=True,
            text=True
        )
        duration = float(result.stdout.strip())
    except:
        duration = 0
    
    print(f"📥 Baixado: {output_file} ({size_kb:.1f} KB, {duration:.2f}s)")
    return True

def analyze_noise(audio_file):
    """Analisa nível de ruído do áudio usando ffmpeg stats"""
    try:
        # Usar astats filter do ffmpeg para estatísticas de áudio
        result = subprocess.run([
            'ffmpeg', '-i', audio_file, '-af', 'astats=metadata=1:reset=1', 
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=30)
        
        # Extrair RMS level (aproximação de ruído)
        stderr = result.stderr
        rms_values = []
        for line in stderr.split('\n'):
            if 'RMS level dB' in line:
                try:
                    rms_db = float(line.split(':')[-1].strip())
                    rms_values.append(rms_db)
                except:
                    pass
        
        if rms_values:
            avg_rms = sum(rms_values) / len(rms_values)
            return avg_rms
        
        return None
    except Exception as e:
        print(f"⚠️ Erro ao analisar ruído: {e}")
        return None

def main():
    print("=" * 80)
    print("  🧪 TESTE DE REDUÇÃO DE CHIADO F5-TTS")
    print("=" * 80)
    print(f"📁 Arquivo de áudio: {VOICE_AUDIO}")
    print(f"📝 Texto: {len(TEST_TEXT)} caracteres")
    print()
    
    # Limpar vozes antigas
    cleanup_old_voices()
    
    # Perfis a testar
    profiles = [
        ("f5tts_fast", "Fast"),
        ("f5tts_balanced", "Balanced"),
        ("f5tts_ultra_quality", "Ultra Quality")
    ]
    
    results = []
    
    for profile_id, profile_name in profiles:
        print("\n" + "=" * 80)
        print(f"🎯 TESTANDO: {profile_name.upper()}")
        print("=" * 80)
        
        # Clonar voz
        voice_id = clone_voice(profile_name)
        if not voice_id:
            print(f"❌ Falha ao clonar voz para {profile_name}")
            continue
        
        # Gerar áudio
        job_id = generate_audio(voice_id, profile_id, profile_name)
        if not job_id:
            print(f"❌ Falha ao gerar áudio para {profile_name}")
            continue
        
        # Download
        output_file = f"output_chiado_{profile_id}.wav"
        if not download_audio(job_id, output_file):
            print(f"❌ Falha ao baixar áudio para {profile_name}")
            continue
        
        # Análise de ruído
        noise_level = analyze_noise(output_file)
        
        # Salvar resultado
        results.append({
            'profile_id': profile_id,
            'profile_name': profile_name,
            'voice_id': voice_id,
            'job_id': job_id,
            'output_file': output_file,
            'noise_level_db': noise_level
        })
        
        print(f"✅ {profile_name} completo!")
    
    # Relatório final
    print("\n" + "=" * 80)
    print("📊 RESULTADOS FINAIS")
    print("=" * 80)
    
    for r in results:
        print(f"\n{r['profile_name'].upper()}:")
        print(f"  Profile ID: {r['profile_id']}")
        print(f"  Voice ID: {r['voice_id']}")
        print(f"  Arquivo: {r['output_file']}")
        if r['noise_level_db'] is not None:
            print(f"  Nível de Ruído: {r['noise_level_db']:.2f} dB")
        else:
            print(f"  Nível de Ruído: N/A")
    
    # Comparação
    if len(results) >= 2:
        print("\n📈 COMPARAÇÃO:")
        noise_levels = [(r['profile_name'], r['noise_level_db']) 
                       for r in results if r['noise_level_db'] is not None]
        
        if noise_levels:
            noise_levels.sort(key=lambda x: x[1])  # Menor ruído primeiro
            print(f"  🏆 Melhor (menos ruído): {noise_levels[0][0]} ({noise_levels[0][1]:.2f} dB)")
            print(f"  ⚠️ Pior (mais ruído): {noise_levels[-1][0]} ({noise_levels[-1][1]:.2f} dB)")
            
            diff = noise_levels[-1][1] - noise_levels[0][1]
            print(f"  📊 Diferença: {diff:.2f} dB")
    
    # Comandos de reprodução
    print("\n🎧 REPRODUZIR:")
    for r in results:
        print(f"  ffplay -autoexit {r['output_file']}  # {r['profile_name']}")
    
    print("\n✅ Teste concluído!")

if __name__ == "__main__":
    main()
