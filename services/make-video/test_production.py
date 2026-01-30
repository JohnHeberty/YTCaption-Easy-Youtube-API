#!/usr/bin/env python3
"""
Teste de Produção - Make Video Service
Simula instalação do zero e teste real completo
"""

import sys
import asyncio
import httpx
import subprocess
from pathlib import Path
from datetime import datetime

API_URL = "http://localhost:8004"
AUDIO_FILE = "/root/YTCaption-Easy-Youtube-API/services/make-video/TEST.ogg"


async def main():
    print("\n" + "="*80)
    print("🔥 TESTE DE FOGO - MAKE VIDEO SERVICE")
    print("="*80)
    print(f"🕐 Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Health Check
    print("1️⃣ Health Check...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_URL}/health")
            resp.raise_for_status()
            health = resp.json()
            print(f"   ✅ API: {health['status']}")
            print(f"   📦 Redis: {health['redis']}")
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
            return 1
    
    # 2. Verificar áudio
    print("\n2️⃣ Verificando áudio TEST.ogg...")
    audio_path = Path(AUDIO_FILE)
    if not audio_path.exists():
        print(f"   ❌ Arquivo não encontrado: {AUDIO_FILE}")
        return 1
    
    size_kb = audio_path.stat().st_size / 1024
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
         '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip()) if result.returncode == 0 else 0
    
    print(f"   ✅ Tamanho: {size_kb:.1f} KB")
    print(f"   ✅ Duração: {duration:.2f}s")
    
    # 3. Criar job
    print("\n3️⃣ Criando job de processamento...")
    async with httpx.AsyncClient(timeout=300.0) as client:
        with open(AUDIO_FILE, 'rb') as f:
            files = {'audio_file': ('TEST.ogg', f, 'audio/ogg')}
            data = {
                'query': 'satisfying asmr relaxing sounds',
                'max_shorts': 10,
                'aspect_ratio': '9:16',
                'subtitle_style': 'dynamic'
            }
            
            try:
                resp = await client.post(f"{API_URL}/make-video", files=files, data=data)
                resp.raise_for_status()
                result = resp.json()
                job_id = result['job_id']
                print(f"   ✅ Job criado: {job_id}")
            except Exception as e:
                print(f"   ❌ ERRO: {e}")
                return 1
        
        # 4. Monitorar progresso
        print("\n4️⃣ Monitorando progresso...")
        print("   " + "-"*76)
        
        last_status = None
        start_time = datetime.now()
        
        while True:
            await asyncio.sleep(3)
            
            try:
                resp = await client.get(f"{API_URL}/jobs/{job_id}")
                resp.raise_for_status()
                job = resp.json()
                
                status = job['status']
                progress = job.get('progress', 0)
                elapsed = (datetime.now() - start_time).total_seconds()
                
                if status != last_status:
                    status_emoji = {
                        'queued': '⏳',
                        'analyzing_audio': '🎵',
                        'fetching_shorts': '🔍',
                        'downloading_shorts': '⬇️',
                        'selecting_shorts': '🎲',
                        'assembling_video': '🎬',
                        'generating_subtitles': '📝',
                        'final_composition': '🎨',
                        'completed': '✅',
                        'failed': '❌'
                    }.get(status, '📊')
                    
                    print(f"   {status_emoji} [{int(elapsed):3d}s] {status:30s} {progress:5.1f}%")
                    last_status = status
                
                if status == 'completed':
                    print("   " + "-"*76)
                    print(f"\n   ✅ JOB COMPLETADO!")
                    print(f"   📹 Vídeo: {job.get('video_url', 'N/A')}")
                    print(f"   ⏱️  Duração: {job.get('duration', 0):.1f}s")
                    
                    # Verificar arquivo
                    video_path = Path(f"storage/output_videos/{job_id}_final.mp4")
                    if video_path.exists():
                        size_mb = video_path.stat().st_size / (1024 * 1024)
                        print(f"   💾 Tamanho: {size_mb:.1f} MB")
                        
                        # Duração real
                        result = subprocess.run(
                            ['ffprobe', '-v', 'error', '-show_entries', 
                             'format=duration', '-of', 
                             'default=noprint_wrappers=1:nokey=1', str(video_path)],
                            capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            real_duration = float(result.stdout.strip())
                            print(f"   🎬 Duração real: {real_duration:.2f}s")
                            
                            # Verificar sincronização
                            diff = abs(real_duration - duration)
                            if diff < 0.5:
                                print(f"   ✅ Sincronização perfeita! (diff: {diff:.2f}s)")
                            else:
                                print(f"   ⚠️  Diferença: {diff:.2f}s")
                    
                    print()
                    return 0
                
                elif status == 'failed':
                    print("   " + "-"*76)
                    print(f"\n   ❌ JOB FALHOU!")
                    print(f"   Erro: {job.get('error_message', 'Desconhecido')}")
                    print()
                    return 1
                    
            except Exception as e:
                print(f"   ⚠️  Erro ao verificar status: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        
        print("="*80)
        print("🏁 TESTE FINALIZADO")
        print("="*80)
        print()
        
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
        sys.exit(1)
