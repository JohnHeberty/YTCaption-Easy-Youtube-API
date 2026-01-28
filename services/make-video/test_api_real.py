#!/usr/bin/env python3
"""
TESTE 100% REAL - API COMPLETA
Pipeline: busca → download → concat → áudio → transcrição → legendas → vídeo final
SEM MOCKS, SEM FAKE, TUDO REAL!
"""
import asyncio
import os
from pathlib import Path
import httpx

async def test_api_real():
    """Teste completo pela API real"""
    
    print("=" * 80)
    print("🎯 TESTE REAL - API COMPLETA")
    print("=" * 80)
    print()
    
    # API URL
    api_url = "http://localhost:8004"
    
    print(f"📡 API: {api_url}")
    print()
    
    # 1. Preparar áudio
    audio_path = Path(__file__).parent / "storage" / "audio_uploads" / "test_audio.ogg"
    
    if not audio_path.parent.exists():
        audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Usar áudio existente ou criar um
    if not audio_path.exists():
        # Criar áudio silencioso de 11s
        print("🎵 Criando áudio de teste...")
        os.system(f"ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 11 -q:a 9 -acodec libvorbis {audio_path} -y 2>/dev/null")
    
    print(f"🎵 Áudio: {audio_path.name} ({audio_path.stat().st_size / 1024:.1f} KB)")
    print()
    
    # 2. Criar job via API
    print("📤 Criando job via POST /make-video")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Upload file
        with open(audio_path, "rb") as f:
            files = {"audio_file": (audio_path.name, f, "audio/ogg")}
            data = {
                "query": "satisfying asmr relaxing",
                "subtitle_language": "pt",
                "max_shorts": 10
            }
            
            try:
                response = await client.post(
                    f"{api_url}/make-video",
                    files=files,
                    data=data
                )
                
                if response.status_code not in [200, 202]:
                    print(f"❌ Erro na API: {response.status_code}")
                    print(response.text)
                    return
                
                result = response.json()
                task_id = result.get("job_id") or result.get("task_id")
                
                print(f"✅ Job criado: {task_id}")
                print()
                
            except Exception as e:
                print(f"❌ Erro ao criar job: {e}")
                return
        
        # 3. Monitorar progresso
        print("⏳ Monitorando progresso...")
        print()
        
        max_checks = 120  # 10 minutos (5s por check)
        
        for i in range(max_checks):
            try:
                status_response = await client.get(
                    f"{api_url}/jobs/{task_id}"
                )
                
                if status_response.status_code != 200:
                    print(f"⚠️  Erro ao checar status: {status_response.status_code}")
                    await asyncio.sleep(5)
                    continue
                
                status = status_response.json()
                state = status["status"]
                progress = status.get("progress", 0)
                current_step = status.get("current_step", "")
                
                # Converter progress para int
                progress_int = int(progress) if progress else 0
                
                # Mostrar progresso
                if i % 6 == 0 or state in ["SUCCESS", "FAILURE", "completed", "failed"]:  # A cada 30s ou final
                    print(f"[{i*5:3d}s] {state:10s} | {progress_int:3d}% | {current_step}")
                
                if state == "SUCCESS":
                    print()
                    print("✅ VÍDEO CRIADO COM SUCESSO!")
                    print()
                    
                    video_url = status.get("video_url")
                    if video_url:
                        print(f"📹 URL: {video_url}")
                        
                        # Baixar vídeo
                        video_response = await client.get(f"{api_url}{video_url}")
                        if video_response.status_code == 200:
                            output_path = Path(__file__).parent / "storage" / "output_videos" / "API_TEST_FINAL.mp4"
                            output_path.write_bytes(video_response.content)
                            print(f"💾 Salvo: {output_path}")
                            print(f"📏 Tamanho: {len(video_response.content) / 1024 / 1024:.2f} MB")
                    
                    # Metadados
                    metadata = status.get("metadata", {})
                    print()
                    print("📊 METADADOS:")
                    print(f"   Vídeos baixados: {metadata.get('videos_downloaded', 0)}")
                    print(f"   Segmentos transcritos: {metadata.get('transcription_segments', 0)}")
                    print(f"   Legendas geradas: {metadata.get('subtitles_count', 0)}")
                    print(f"   Duração: {metadata.get('duration', 0):.1f}s")
                    print()
                    
                    break
                
                elif state == "FAILURE":
                    print()
                    print(f"❌ FALHA: {status.get('error')}")
                    print()
                    break
                
                await asyncio.sleep(5)
            
            except Exception as e:
                print(f"⚠️  Erro ao monitorar: {e}")
                await asyncio.sleep(5)
        
        else:
            print()
            print("❌ Timeout - job não completou em 10 minutos")
            print()
    
    print("=" * 80)
    print("🏁 TESTE CONCLUÍDO")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_real())
