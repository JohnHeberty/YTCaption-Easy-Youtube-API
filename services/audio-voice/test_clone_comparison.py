#!/usr/bin/env python3
"""
Script de teste: Comparação XTTS vs F5-TTS
Clona voz com Teste.ogg e gera áudio com ambos os engines
"""
import requests
import time
import json
from pathlib import Path

API_URL = "http://localhost:8005"
AUDIO_FILE = Path("tests/Teste.ogg")

# Texto longo para testar qualidade
TEXTO_GERACAO = """
Boa noite, meus caros ouvintes! Essa mensagem está sendo gerada por inteligência artificial 
utilizando tecnologia avançada de clonagem de voz. Estamos testando dois motores diferentes 
de síntese de fala: o XTTS, que é rápido e eficiente, e o F5-TTS, que oferece qualidade 
premium com maior naturalidade e expressividade. Cada motor tem suas características únicas, 
e hoje vamos descobrir qual deles produz o melhor resultado para esta voz específica. 
Vamos começar essa jornada fascinante pelo mundo da síntese de voz neural!
"""

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print('='*80)

def clone_voice(engine: str, audio_file: Path):
    """Clona voz usando engine especificado"""
    print(f"\n🎤 Clonando voz com {engine.upper()}...")
    
    with open(audio_file, 'rb') as f:
        files = {'file': (audio_file.name, f, 'audio/ogg')}
        data = {
            'name': f'Voz Teste {engine.upper()}',
            'language': 'pt-BR',
            'description': f'Voz clonada usando {engine.upper()} para comparação',
            'tts_engine': engine
        }
        
        response = requests.post(f"{API_URL}/voices/clone", files=files, data=data)
        
    if response.status_code == 202:
        result = response.json()
        job_id = result['job_id']
        print(f"✅ Job de clonagem criado: {job_id}")
        return job_id
    else:
        print(f"❌ Erro ao clonar: {response.status_code}")
        print(response.text)
        return None

def wait_for_job(job_id: str, timeout: int = 120):
    """Aguarda conclusão do job"""
    print(f"⏳ Aguardando conclusão do job {job_id}...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{API_URL}/jobs/{job_id}")
        if response.status_code == 200:
            job = response.json()
            status = job['status']
            progress = job.get('progress', 0)
            
            if status == 'completed':
                print(f"✅ Job concluído!")
                return job
            elif status == 'failed':
                print(f"❌ Job falhou: {job.get('error_message')}")
                return None
            else:
                print(f"  Status: {status} ({progress:.1f}%)", end='\r')
        
        time.sleep(2)
    
    print(f"❌ Timeout aguardando job")
    return None

def generate_audio(voice_id: str, engine: str, text: str):
    """Gera áudio usando voz clonada"""
    print(f"\n🔊 Gerando áudio com {engine.upper()}...")
    
    # Determina quality_profile_id baseado no engine
    quality_profile_id = f"{engine}_balanced"
    
    data = {
        'text': text,
        'source_language': 'pt-BR',
        'mode': 'dubbing_with_clone',
        'voice_id': voice_id,
        'tts_engine': engine,
        'quality_profile_id': quality_profile_id
    }
    
    response = requests.post(f"{API_URL}/jobs", data=data)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result['id']
        print(f"✅ Job de geração criado: {job_id}")
        return job_id
    else:
        print(f"❌ Erro ao gerar: {response.status_code}")
        print(response.text)
        return None

def download_audio(job_id: str, output_file: str):
    """Baixa áudio gerado"""
    print(f"📥 Baixando áudio para {output_file}...")
    
    response = requests.get(f"{API_URL}/jobs/{job_id}/download?format=wav")
    
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        file_size = Path(output_file).stat().st_size / 1024  # KB
        print(f"✅ Áudio salvo: {output_file} ({file_size:.1f} KB)")
        return True
    else:
        print(f"❌ Erro ao baixar: {response.status_code}")
        return False

def get_voices():
    """Lista vozes disponíveis"""
    response = requests.get(f"{API_URL}/voices?limit=100")
    if response.status_code == 200:
        return response.json()['voices']
    return []

def main():
    print_section("🧪 TESTE DE COMPARAÇÃO: XTTS vs F5-TTS")
    
    if not AUDIO_FILE.exists():
        print(f"❌ Arquivo não encontrado: {AUDIO_FILE}")
        return
    
    print(f"📁 Arquivo de áudio: {AUDIO_FILE}")
    print(f"📝 Texto para geração ({len(TEXTO_GERACAO)} caracteres)")
    
    # Limpar vozes antigas com mesmo nome
    print_section("🧹 Limpando vozes antigas")
    voices = get_voices()
    for voice in voices:
        if 'Voz Teste' in voice['name']:
            print(f"🗑️  Removendo voz antiga: {voice['name']} ({voice['id']})")
            requests.delete(f"{API_URL}/voices/{voice['id']}")
    
    results = {}
    
    # Testar ambos os engines
    for engine in ['xtts', 'f5tts']:
        print_section(f"🎯 TESTANDO {engine.upper()}")
        
        # 1. Clonar voz
        clone_job_id = clone_voice(engine, AUDIO_FILE)
        if not clone_job_id:
            continue
        
        # 2. Aguardar clonagem
        clone_job = wait_for_job(clone_job_id, timeout=180)
        if not clone_job:
            continue
        
        # Extrair voice_id do job (pode estar em diferentes lugares)
        voice_id = None
        if 'voice_id' in clone_job:
            voice_id = clone_job['voice_id']
        else:
            # Buscar na lista de vozes
            voices = get_voices()
            for voice in voices:
                if engine.upper() in voice['name']:
                    voice_id = voice['id']
                    break
        
        if not voice_id:
            print(f"❌ Não foi possível encontrar voice_id para {engine}")
            continue
        
        print(f"🎵 Voice ID: {voice_id}")
        
        # 3. Gerar áudio
        gen_job_id = generate_audio(voice_id, engine, TEXTO_GERACAO)
        if not gen_job_id:
            continue
        
        # 4. Aguardar geração
        gen_job = wait_for_job(gen_job_id, timeout=180)
        if not gen_job:
            continue
        
        # 5. Baixar áudio
        output_file = f"output_comparison_{engine}.wav"
        if download_audio(gen_job_id, output_file):
            results[engine] = {
                'voice_id': voice_id,
                'clone_job_id': clone_job_id,
                'gen_job_id': gen_job_id,
                'output_file': output_file,
                'file_size_kb': Path(output_file).stat().st_size / 1024,
                'duration': gen_job.get('duration')
            }
    
    # Resultados finais
    print_section("📊 RESULTADOS FINAIS")
    
    for engine, data in results.items():
        print(f"\n{engine.upper()}:")
        print(f"  Voice ID: {data['voice_id']}")
        print(f"  Arquivo: {data['output_file']}")
        print(f"  Tamanho: {data['file_size_kb']:.1f} KB")
        if data['duration']:
            print(f"  Duração: {data['duration']:.2f}s")
    
    if len(results) == 2:
        xtts_size = results['xtts']['file_size_kb']
        f5tts_size = results['f5tts']['file_size_kb']
        diff_percent = ((f5tts_size - xtts_size) / xtts_size) * 100
        
        print(f"\n📈 Comparação:")
        print(f"  F5-TTS é {abs(diff_percent):.1f}% {'maior' if diff_percent > 0 else 'menor'} que XTTS")
    
    print_section("✅ TESTE CONCLUÍDO!")
    
    print("\n🎧 Para ouvir os áudios:")
    for engine in results:
        print(f"  ffplay {results[engine]['output_file']}")

if __name__ == '__main__':
    main()
