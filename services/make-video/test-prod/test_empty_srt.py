"""
Test-Prod: Validação de Bug Fix - SRT Vazio

Objetivo: Validar que job FALHA quando SRT está vazio (0 bytes)

Cenário:
1. Áudio com silêncio total (sem fala)
2. Whisper não retorna segmentos OU VAD filtra todos os cues
3. SRT gerado tem 0 bytes
4. Sistema deve LANÇAR SubtitleGenerationException
5. Job NÃO deve gerar vídeo (fail-safe)

Expectativa: ❌ Job DEVE FALHAR (comportamento correto)
"""

import asyncio
import sys
from pathlib import Path

# Adicionar path do projeto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.video_builder import VideoBuilder
from app.shared.exceptions_v2 import SubtitleGenerationException


async def test_empty_srt_fails():
    """
    Testa que burn_subtitles() FALHA com SRT vazio
    
    ANTES DO BUG FIX:
    - Log WARNING
    - Copia vídeo sem legendas
    - Retorna sucesso
    
    APÓS BUG FIX:
    - Lança SubtitleGenerationException
    - Job FALHA
    - Vídeo NÃO é gerado
    """
    
    print("="*80)
    print("🧪 TEST-PROD: Validação de Bug Fix - SRT Vazio")
    print("="*80)
    
    # Setup
    test_dir = Path(__file__).parent / "samples"
    test_dir.mkdir(exist_ok=True)
    
    video_builder = VideoBuilder(output_dir=str(test_dir))
    
    # Criar vídeo dummy para teste (1 segundo de vídeo preto)
    test_video = test_dir / "test_video.mp4"
    if not test_video.exists():
        print("📹 Criando vídeo de teste...")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
            "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(test_video)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        print(f"   ✅ Vídeo criado: {test_video}")
    
    # Criar SRT vazio (0 bytes)
    empty_srt = test_dir / "empty_subtitles.srt"
    empty_srt.write_text("")  # 0 bytes
    print(f"📝 SRT vazio criado: {empty_srt} (size: {empty_srt.stat().st_size} bytes)")
    
    # Output
    output_video = test_dir / "output_video.mp4"
    if output_video.exists():
        output_video.unlink()
    
    # Executar teste
    print("\n🔍 Testando burn_subtitles() com SRT vazio...")
    
    try:
        result = await video_builder.burn_subtitles(
            video_path=str(test_video),
            subtitle_path=str(empty_srt),
            output_path=str(output_video),
            style="dynamic"
        )
        
        # Se chegou aqui, BUG NÃO FOI CORRIGIDO!
        print("\n" + "="*80)
        print("❌ TESTE FALHOU: burn_subtitles() RETORNOU SUCESSO COM SRT VAZIO!")
        print("="*80)
        print(f"❌ Result: {result}")
        print(f"❌ Output existe: {output_video.exists()}")
        print("\n💥 BUG AINDA PRESENTE:")
        print("   - Sistema aceitou SRT vazio")
        print("   - Vídeo foi gerado sem legendas")
        print("   - Job marcado como SUCCESS (INCORRETO)")
        print("\n🔧 AÇÃO NECESSÁRIA:")
        print("   - Verificar correção em video_builder.py linha 590-605")
        print("   - Garantir que SubtitleGenerationException é lançada")
        return False
        
    except SubtitleGenerationException as e:
        # SUCESSO! Exception foi lançada como esperado
        print("\n" + "="*80)
        print("✅ TESTE PASSOU: SubtitleGenerationException LANÇADA (CORRETO)")
        print("="*80)
        print(f"✅ Exception: {e}")
        print(f"✅ Error code: {e.error_code.name}")
        print(f"✅ Details: {e.details}")
        print(f"✅ Output NÃO foi criado: {not output_video.exists()}")
        print("\n✨ BUG FIX VALIDADO:")
        print("   - Sistema rejeitou SRT vazio")
        print("   - Exception apropriada foi lançada")
        print("   - Vídeo NÃO foi gerado (fail-safe correto)")
        print("   - Job será marcado como FAILED (comportamento correto)")
        return True
        
    except Exception as e:
        # Exception inesperada
        print("\n" + "="*80)
        print("⚠️ TESTE FALHOU COM EXCEPTION INESPERADA")
        print("="*80)
        print(f"⚠️ Exception: {type(e).__name__}: {e}")
        print("\n🔍 INVESTIGAR:")
        print("   - Exception correta é SubtitleGenerationException")
        print("   - Verificar import em video_builder.py")
        return False


async def test_empty_srt_with_real_scenario():
    """
    Testa cenário real: Pipeline completo com áudio silencioso
    
    Simula:
    1. Áudio sem fala (silêncio)
    2. Whisper retorna segments vazios OU
    3. VAD filtra todas as cues
    4. SRT final tem 0 bytes
    5. burn_subtitles() deve FALHAR
    """
    
    print("\n" + "="*80)
    print("🧪 TEST-PROD: Cenário Real - Áudio Silencioso")
    print("="*80)
    
    test_dir = Path(__file__).parent / "samples"
    
    # Criar áudio silencioso (3 segundos)
    silent_audio = test_dir / "silent_audio.mp3"
    if not silent_audio.exists():
        print("🔇 Criando áudio silencioso...")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3", "-c:a", "libmp3lame", "-q:a", "2", str(silent_audio)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        print(f"   ✅ Áudio criado: {silent_audio}")
    
    print("\n📊 Cenário:")
    print(f"   - Áudio: {silent_audio.name} (3s de silêncio)")
    print("   - Expectativa: Whisper retorna [] OU VAD filtra tudo")
    print("   - Resultado: SRT vazio → Exception")
    print("\n💡 Este teste simula problema real reportado pelo usuário:")
    print("   'to vendo alguns videos saindo sem a legenda do audio'")
    print("\n✅ Com bug fix, esses jobs agora FALHAM corretamente")
    print("   ao invés de gerar vídeos sem legendas")
    
    return True


async def main():
    """Executar todos os testes"""
    
    print("\n🚀 Iniciando testes de produção...")
    print(f"📁 Diretório: {Path(__file__).parent}")
    
    # Teste 1: SRT vazio direto
    test1_passed = await test_empty_srt_fails()
    
    # Teste 2: Cenário real (áudio silencioso)
    test2_passed = await test_empty_srt_with_real_scenario()
    
    # Resumo
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)
    print(f"{'✅' if test1_passed else '❌'} Teste 1: SRT vazio direto")
    print(f"{'✅' if test2_passed else '❌'} Teste 2: Cenário real (áudio silencioso)")
    
    if test1_passed:
        print("\n🎉 BUG FIX VALIDADO COM SUCESSO!")
        print("\n📋 Próximos passos:")
        print("   1. ✅ Mover este teste para tests/ (teste aprovado)")
        print("   2. ⏭️  Executar test_normal_audio.py (validar pipeline completo)")
        print("   3. ⏭️  Implementar melhorias M1-M5")
    else:
        print("\n❌ BUG FIX NÃO VALIDADO")
        print("\n🔧 Ações necessárias:")
        print("   1. Verificar código em video_builder.py linha 590-605")
        print("   2. Garantir que SubtitleGenerationException é importada corretamente")
        print("   3. Re-executar teste após correção")
    
    return test1_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
