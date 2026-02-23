#!/usr/bin/env python3
"""
Teste de Fogo - SubtitleClassifierV2
Gera vídeo compilation com 30 shorts usando query "Videos Satisfatorios"

Objetivo: Validar TRSD V2 (threshold 0.75) em volume real de produção
"""

import requests
import time
import sys
from pathlib import Path

# Configuração
API_URL = "http://localhost:8004"
AUDIO_FILE = "TEST.ogg"
QUERY = "Videos Satisfatorios"
NUM_VIDEOS = 30

def create_video_task(audio_path: Path, query: str, num_videos: int) -> str:
    """Cria task de make-video e retorna job_id"""
    print(f"\n🎬 Creating make-video task...")
    print(f"  Audio: {audio_path.name}")
    print(f"  Query: {query}")
    print(f"  Max shorts: {num_videos}")
    
    with open(audio_path, 'rb') as f:
        files = {'audio_file': (audio_path.name, f, 'audio/ogg')}
        data = {
            'query': query,
            'max_shorts': num_videos,
            'subtitle_language': 'pt',
            'subtitle_style': 'static',
            'aspect_ratio': '9:16'
        }
        
        response = requests.post(f"{API_URL}/make-video", files=files, data=data)
    
    if response.status_code != 202:
        print(f"❌ Task creation failed: {response.text}")
        sys.exit(1)
    
    result = response.json()
    job_id = result.get('job_id')
    
    print(f"✅ Task created: {job_id}")
    return job_id

def monitor_job(job_id: str):
    """Monitora progresso da job até conclusão"""
    print(f"\n📊 Monitoring job: {job_id}\n")
    print("="*80)
    
    last_status = None
    last_progress = None
    
    while True:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}")
            
            if response.status_code != 200:
                print(f"⚠️ Status check failed: {response.status_code}")
                time.sleep(5)
                continue
            
            data = response.json()
            status = data.get('status')
            progress = data.get('progress', {})
            
            # Log mudanças de status
            if status != last_status:
                print(f"\n🔄 Status: {status}")
                last_status = status
            
            # Log progresso
            if progress != last_progress:
                current = progress.get('current', 0)
                total = progress.get('total', 0)
                message = progress.get('message', '')
                
                if total > 0:
                    percent = (current / total) * 100
                    print(f"  [{current}/{total}] {percent:.1f}% - {message}")
                else:
                    print(f"  {message}")
                
                last_progress = progress
            
            # Verificar estados finais
            if status == 'completed':
                print("\n" + "="*80)
                print("✅ JOB COMPLETED!")
                print("="*80)
                
                result = data.get('result', {})
                
                # Estatísticas de processamento
                print(f"\n📊 PROCESSING STATISTICS:")
                print(f"  Total shorts requested: {NUM_VIDEOS}")
                
                if 'shorts_used' in result:
                    print(f"  Shorts used in video: {result['shorts_used']}")
                
                if 'output_path' in result:
                    print(f"  Output file: {result['output_path']}")
                
                if 'duration' in result:
                    print(f"  Duration: {result['duration']}s")
                
                # Verificar se há informações de TRSD
                trsd_stats = data.get('trsd_stats', {})
                if trsd_stats:
                    print(f"\n🎯 TRSD V2 STATISTICS:")
                    print(f"  Videos analyzed: {trsd_stats.get('analyzed', 0)}")
                    print(f"  Videos approved: {trsd_stats.get('approved', 0)}")
                    print(f"  Videos blocked: {trsd_stats.get('blocked', 0)}")
                    print(f"  False positives recovered: {trsd_stats.get('recovered_fp', 0)}")
                
                break
                
            elif status == 'failed':
                print("\n" + "="*80)
                print("❌ JOB FAILED!")
                print("="*80)
                
                error = data.get('error', 'Unknown error')
                print(f"  Error: {error}")
                break
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Monitoring interrupted by user")
            print(f"Job {job_id} is still running on the server")
            break
        except Exception as e:
            print(f"⚠️ Error monitoring job: {e}")
            time.sleep(5)

def main():
    print("="*80)
    print("🔥 TESTE DE FOGO - SubtitleClassifierV2 (threshold 0.75)")
    print("="*80)
    print()
    
    # Verificar se audio existe
    audio_path = Path(AUDIO_FILE)
    if not audio_path.exists():
        print(f"❌ Audio file not found: {AUDIO_FILE}")
        return 1
    
    print(f"📁 Audio file: {audio_path}")
    print(f"📏 Size: {audio_path.stat().st_size / 1024:.1f} KB")
    print()
    
    # Criar job
    job_id = create_video_task(audio_path, QUERY, NUM_VIDEOS)
    
    # Monitorar
    monitor_job(job_id)
    
    print()
    print("="*80)
    print("🎬 Fire test completed!")
    print("="*80)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
