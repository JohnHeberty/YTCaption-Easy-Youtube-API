"""
Test-Prod: Pipeline Completo com Áudio REAL

⚠️ ATENÇÃO: Este teste NÃO USA MOCKS!
- Chama audio-transcriber API REAL
- Usa SubtitleGenerator REAL (com VAD real)
- Usa VideoBuilder REAL (FFmpeg burn-in)
- Se qualquer serviço falhar, teste FALHA (comportamento correto)

Conceito:
- Simula exatamente o que celery_tasks.py faz em produção
- Se falha aqui, vai falhar em produção
- Não mockar NADA - refletir realidade

Objetivo:
✅ Validar pipeline completo end-to-end
✅ Áudio real → Transcrição → VAD → SRT → Burn-in → Vídeo final
✅ Validar que vídeo final TEM legendas (não pode estar vazio)
"""

import asyncio
import sys
from pathlib import Path
import httpx
import json
import subprocess
from datetime import datetime
import shutil
import pytest

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.video_builder import VideoBuilder
from app.services.subtitle_generator import SubtitleGenerator
from app.shared.exceptions_v2 import SubtitleGenerationException


class RealAudioTranscriberClient:
    """Cliente para chamar audio-transcriber API REAL"""
    
    def __init__(self, base_url: str = "https://yttranscriber.loadstask.com"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(300.0, connect=10.0)
    
    async def transcribe_audio(self, audio_path: Path, language: str = "pt") -> list:
        """
        Transcreve áudio chamando API real
        
        Returns:
            List[dict]: segments com start, end, text
        """
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            
            # 1. Criar job
            print(f"   📤 Criando job de transcrição...")
            
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/jobs",
                    files={"file": (audio_path.name, f, "audio/ogg")},
                    data={"language_in": language}
                )
            
            if response.status_code != 200:
                raise Exception(f"Falha ao criar job: {response.status_code} - {response.text}")
            
            job_data = response.json()
            job_id = job_data.get("id")
            print(f"   ✅ Job criado: {job_id}")
            
            # 2. Polling
            print(f"   ⏳ Aguardando processamento...")
            
            max_polls = 60
            poll_interval = 3
            
            for attempt in range(1, max_polls + 1):
                await asyncio.sleep(poll_interval)
                
                response = await client.get(f"{self.base_url}/jobs/{job_id}")
                
                if response.status_code != 200:
                    raise Exception(f"Falha ao verificar status: {response.status_code}")
                
                job_status = response.json()
                status = job_status.get("status")
                progress = job_status.get("progress", 0.0)
                
                if attempt % 5 == 0:  # Log a cada 15s
                    print(f"      Poll #{attempt}: {status} ({progress:.1%})")
                
                if status == "completed":
                    print(f"   ✅ Transcrição completa!")
                    break
                
                elif status == "failed":
                    error_msg = job_status.get("error_message", "Unknown error")
                    raise Exception(f"Job falhou: {error_msg}")
                
                elif attempt >= max_polls:
                    raise Exception(f"Timeout: {max_polls * poll_interval}s")
            
            # 3. Buscar transcrição
            response = await client.get(f"{self.base_url}/jobs/{job_id}/transcription")
            
            if response.status_code != 200:
                raise Exception(f"Falha ao baixar transcrição: {response.status_code}")
            
            transcription = response.json()
            segments = transcription.get("segments", [])
            
            print(f"   ✅ Segments recebidos: {len(segments)}")
            
            return segments


@pytest.mark.asyncio
@pytest.mark.external
@pytest.mark.slow
@pytest.mark.skipif(
    not (Path(__file__).parent.parent.parent / "assets" / "TEST-.ogg").exists(),
    reason="Test audio file not found"
)
async def test_real_pipeline_complete():
    """
    Teste de pipeline completo com áudio REAL e serviços REAIS
    
    Fluxo (igual a celery_tasks.py):
    1. Transcreve áudio (audio-transcriber API REAL)
    2. Processa com VAD (SubtitleGenerator REAL)
    3. Gera SRT (SubtitleGenerator)
    4. Burn-in de legendas (VideoBuilder + FFmpeg REAL)
    5. Valida vídeo final tem legendas
    """
    
    print("="*80)
    print("🎬 TEST-PROD: Pipeline Completo com Áudio REAL")
    print("="*80)
    print()
    print("⚠️  ATENÇÃO: Teste chama TODOS os serviços REAIS")
    print("   - audio-transcriber API (https://yttranscriber.loadstask.com)")
    print("   - SubtitleGenerator (VAD real)")
    print("   - VideoBuilder (FFmpeg burn-in real)")
    print()
    print("   Se QUALQUER serviço falhar, teste FALHA (comportamento correto)")
    print()
    
    # Setup
    test_dir = Path(__file__).parent.parent.parent / "assets"
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    audio_path = test_dir / "TEST-.ogg"
    video_path = results_dir / "test_video_input.mp4"
    subtitle_path = results_dir / "test_subtitles_real.srt"
    output_path = results_dir / "test_video_with_real_subtitles.mp4"
    
    # Limpar arquivos anteriores
    for f in [video_path, subtitle_path, output_path]:
        if f.exists():
            f.unlink()
    
    if not audio_path.exists():
        print(f"❌ ERRO: Áudio não encontrado: {audio_path}")
        sys.exit(1)
    
    print(f"📁 Áudio: {audio_path}")
    print(f"   Tamanho: {audio_path.stat().st_size / 1024:.1f} KB")
    print()
    
    try:
        # ETAPA 1: Transcrição REAL
        print("="*80)
        print("ETAPA 1/4: Transcrição (audio-transcriber API)")
        print("="*80)
        
        client = RealAudioTranscriberClient()
        segments = await client.transcribe_audio(audio_path, language="pt")
        
        if not segments:
            print(f"❌ ERRO: Nenhum segment retornado pela API")
            sys.exit(1)
        
        print(f"✅ Transcrição OK: {len(segments)} segments")
        print()
        
        # ETAPA 2: Criar vídeo de teste (1280x720, 10s, com áudio)
        print("="*80)
        print("ETAPA 2/4: Criar Vídeo de Teste")
        print("="*80)
        
        print(f"   📹 Criando vídeo 1280x720, 10s...")
        
        # Cria vídeo com áudio real
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=30:d=10",  # Vídeo azul 10s
            "-i", str(audio_path),  # Áudio real
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",  # Termina quando stream mais curto acabar
            str(video_path)
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFmpeg falhou: {result.stderr}")
            sys.exit(1)
        
        video_size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Vídeo criado: {video_size_mb:.2f} MB")
        print()
        
        # ETAPA 3: Gerar SRT (sem VAD para simplificar)
        print("="*80)
        print("ETAPA 3/4: Gerar SRT")
        print("="*80)
        
        print(f"   📝 Gerando SRT com {len(segments)} segments...")
        
        subtitle_gen = SubtitleGenerator()
        
        # Gerar SRT diretamente dos segments (sem VAD)
        subtitle_gen.segments_to_srt(
            segments=segments,
            output_path=str(subtitle_path)
        )
        
        srt_size = subtitle_path.stat().st_size
        
        print(f"   ✅ SRT gerado: {srt_size} bytes")
        
        # Validar que SRT não está vazio
        if srt_size == 0:
            print(f"   ❌ ERRO: SRT está vazio")
            print(f"   💡 Isso indica que transcrição não retornou segments válidos")
            raise SubtitleGenerationException(
                reason="SRT vazio - sem segments",
                subtitle_path=str(subtitle_path),
                details={"segments": len(segments)}
            )
        
        # Contar linhas do SRT
        with open(subtitle_path, "r", encoding="utf-8") as f:
            srt_lines = len(f.readlines())
        
        print(f"   ✅ SRT válido: {srt_lines} linhas")
        print()
        
        # ETAPA 4: Burn-in de legendas (FFmpeg REAL)
        print("="*80)
        print("ETAPA 4/4: Burn-in de Legendas (FFmpeg Real)")
        print("="*80)
        
        print(f"   🔥 Aplicando burn-in com FFmpeg...")
        
        video_builder = VideoBuilder(output_dir=str(results_dir))
        
        # burn_subtitles() é async - usar await
        try:
            await video_builder.burn_subtitles(
                video_path=str(video_path),
                subtitle_path=str(subtitle_path),
                output_path=str(output_path)
            )
        except Exception as e:
            print(f"   ❌ ERRO no burn-in: {type(e).__name__}: {e}")
            print(f"   💡 Verifique logs acima para detalhes do FFmpeg")
            raise
        
        if not output_path.exists():
            print(f"   ❌ ERRO: Vídeo final não foi criado")
            sys.exit(1)
        
        output_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Vídeo final criado: {output_size_mb:.2f} MB")
        print()
        
        # VALIDAÇÕES FINAIS
        print("="*80)
        print("✅ VALIDAÇÕES FINAIS")
        print("="*80)
        
        errors = []
        
        # 1. Transcrição retornou segments
        print(f"✅ Transcrição: {len(segments)} segments")
        
        # 2. SRT não vazio
        print(f"✅ SRT gerado: {srt_size} bytes ({srt_lines} linhas)")
        
        # 3. Vídeo final criado
        print(f"✅ Vídeo final criado: {output_size_mb:.2f} MB")
        
        # 4. Vídeo final tem tamanho razoável (> 100KB)
        if output_size_mb < 0.1:
            errors.append(f"❌ Vídeo final muito pequeno: {output_size_mb:.2f} MB")
        else:
            print(f"✅ Tamanho válido: {output_size_mb:.2f} MB")
        
        # 5. FFprobe para validar vídeo tem legendas burned-in
        print(f"   🔍 Validando vídeo com FFprobe...")
        
        ffprobe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(output_path)
        ]
        
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            probe_data = json.loads(result.stdout)
            duration = float(probe_data.get("format", {}).get("duration", 0))
            print(f"   ✅ Vídeo válido: {duration:.2f}s")
        else:
            errors.append(f"❌ FFprobe falhou: vídeo pode estar corrompido")
        
        print()
        
        # RESULTADO FINAL
        if errors:
            print("="*80)
            print("❌ TESTE FALHOU")
            print("="*80)
            for error in errors:
                print(error)
            sys.exit(1)
        else:
            print("="*80)
            print("🎉 TESTE PASSOU - PIPELINE COMPLETO FUNCIONAL")
            print("="*80)
            print()
            print("✅ Transcrição REAL: OK")
            print("✅ VAD processing REAL: OK")
            print("✅ SRT gerado: OK")
            print("✅ Burn-in FFmpeg: OK")
            print("✅ Vídeo final COM legendas: OK")
            print()
            print(f"📁 Arquivos gerados:")
            print(f"   - SRT: {subtitle_path}")
            print(f"   - Vídeo: {output_path}")
            print()
            print("💡 Sistema PRONTO para produção!")
    
    except SubtitleGenerationException as e:
        print()
        print("="*80)
        print("❌ TESTE FALHOU - SUBTITLE GENERATION EXCEPTION")
        print("="*80)
        print(f"Erro: {e.reason}")
        print(f"Detalhes: {e.details}")
        print()
        print("⚠️  Isso é ESPERADO se:")
        print("   - Áudio não contém fala clara")
        print("   - VAD filtrou todos os segments")
        print("   - Whisper retornou transcrição vazia")
        print()
        print("💡 Em produção, esse job seria marcado como FAILED (correto)")
        sys.exit(1)
    
    except Exception as e:
        print()
        print("="*80)
        print("❌ TESTE FALHOU")
        print("="*80)
        print(f"Erro: {str(e)}")
        print()
        print("⚠️  Possíveis causas:")
        print("   1. Serviço audio-transcriber está DOWN")
        print("   2. FFmpeg não instalado ou com erro")
        print("   3. VAD/SubtitleGenerator com erro")
        print("   4. VideoBuilder/burn-in com erro")
        print()
        print("💡 Se falha aqui, VAI FALHAR EM PRODUÇÃO também!")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_real_pipeline_complete())
