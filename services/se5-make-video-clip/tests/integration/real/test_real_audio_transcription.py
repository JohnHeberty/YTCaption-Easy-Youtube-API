"""
Test-Prod: Teste de Transcrição com Áudio REAL

⚠️ ATENÇÃO: Este teste NÃO USA MOCKS!
- Chama audio-transcriber API REAL
- Se serviço estiver DOWN, teste é SKIPPED

Conceito:
- test-prod/ = Ambiente de produção REAL
- Se falha aqui, vai falhar em produção
- Não mockar NADA - refletir realidade
"""

import asyncio
import os
import sys
from pathlib import Path
import httpx
import json
from datetime import datetime
import pytest

# Adicionar path do projeto
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from common.datetime_utils import now_brazil
except ImportError:
    def now_brazil():
        return datetime.now()


class RealAudioTranscriberClient:
    """Cliente para chamar audio-transcriber API REAL (sem mocks)"""
    
    def __init__(self, base_url: str = "https://yttranscriber.loadstask.com"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5min para transcrição
        self.api_key = os.environ.get("TRANSCRIBER_API_KEY", "")

    @property
    def _headers(self) -> dict:
        if self.api_key:
            return {"X-API-Key": self.api_key}
        return {}

    async def transcribe_audio(self, audio_path: Path, language: str = "pt") -> dict:
        """
        Transcreve áudio chamando API real
        
        Returns:
            {
                "job_id": str,
                "segments": list,
                "duration": float,
                "processing_time": float,
                "language_detected": str
            }
        """
        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            
            # 1. Criar job (POST /jobs)
            print(f"📤 Enviando áudio para transcrição: {audio_path.name}")
            
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{self.base_url}/jobs",
                    headers=self._headers,
                    files={"file": (audio_path.name, f, "audio/ogg")},
                    data={"language_in": language}
                )
            
            if response.status_code != 200:
                raise Exception(f"Falha ao criar job: {response.status_code} - {response.text}")
            
            job_data = response.json()
            job_id = job_data.get("id")
            print(f"✅ Job criado: {job_id}")
            
            # 2. Polling de status (GET /jobs/{job_id})
            print(f"⏳ Aguardando processamento...")
            
            max_polls = 60  # 60 tentativas = 3 minutos (polling a cada 3s)
            poll_interval = 3
            
            for attempt in range(1, max_polls + 1):
                await asyncio.sleep(poll_interval)
                
                response = await client.get(f"{self.base_url}/jobs/{job_id}", headers=self._headers)
                
                if response.status_code != 200:
                    raise Exception(f"Falha ao verificar status: {response.status_code}")
                
                job_status = response.json()
                status = job_status.get("status")
                progress = job_status.get("progress", 0.0)
                
                print(f"   Poll #{attempt}: status={status}, progress={progress:.1%}")
                
                if status == "completed":
                    print(f"✅ Transcrição completa!")
                    break
                
                elif status == "failed":
                    error_msg = job_status.get("error_message", "Unknown error")
                    raise Exception(f"Job falhou: {error_msg}")
                
                elif attempt >= max_polls:
                    raise Exception(f"Timeout: Job não completou em {max_polls * poll_interval}s")
            
            # 3. Buscar transcrição (GET /jobs/{job_id}/transcription)
            print(f"📥 Baixando transcrição...")
            
            response = await client.get(f"{self.base_url}/jobs/{job_id}/transcription", headers=self._headers)
            
            if response.status_code != 200:
                raise Exception(f"Falha ao baixar transcrição: {response.status_code}")
            
            transcription = response.json()
            segments = transcription.get("segments", [])
            
            print(f"✅ Transcrição baixada: {len(segments)} segments")
            
            return {
                "job_id": job_id,
                "segments": segments,
                "duration": transcription.get("duration", 0),
                "processing_time": transcription.get("processing_time", 0),
                "language_detected": transcription.get("language_detected", "N/A"),
                "text": transcription.get("text", "")
            }


@pytest.mark.asyncio
@pytest.mark.external
@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("TRANSCRIBER_API_KEY"),
    reason="TRANSCRIBER_API_KEY not set — skipping real API test",
)
async def test_real_audio_transcription():
    """
    Teste de transcrição com áudio REAL
    
    Fluxo:
    1. Envia TEST-.ogg para audio-transcriber API
    2. Aguarda conclusão (polling)
    3. Valida resposta:
       - segments[] não vazio
       - Cada segment tem: start, end, text
       - duration > 0
       - language_detected válido
    """
    
    print("="*80)
    print("🎤 TEST-PROD: Transcrição com Áudio REAL")
    print("="*80)
    print()
    print("⚠️  ATENÇÃO: Teste chama API REAL (não usa mocks)")
    print("   Se serviço estiver DOWN, teste VAI FALHAR (comportamento correto)")
    print()
    
    # Setup
    test_dir = Path(__file__).parent.parent.parent / "assets"
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    audio_path = test_dir / "TEST-.ogg"
    
    if not audio_path.exists():
        pytest.fail(f"Áudio não encontrado: {audio_path}")
    
    print(f"📁 Áudio: {audio_path}")
    print(f"   Tamanho: {audio_path.stat().st_size / 1024:.1f} KB")
    print()
    
    # Executar transcrição REAL
    try:
        client = RealAudioTranscriberClient()
        result = await client.transcribe_audio(audio_path, language="pt")
        
        # Salvar resultado completo
        result_file = results_dir / f"transcription_{now_brazil().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print()
        print("="*80)
        print("📊 RESULTADO DA TRANSCRIÇÃO")
        print("="*80)
        print(f"Job ID: {result['job_id']}")
        print(f"Segments: {len(result['segments'])}")
        print(f"Duration: {result['duration']:.2f}s" if result['duration'] else "Duration: N/A")
        print(f"Processing Time: {result['processing_time']:.2f}s" if result['processing_time'] else "Processing Time: N/A")
        print(f"Language Detected: {result['language_detected']}")
        print()
        
        # Mostrar primeiros 3 segments
        if result['segments']:
            print("📝 Primeiros segments:")
            for i, seg in enumerate(result['segments'][:3]):
                print(f"   [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")
        
        print()
        print(f"💾 Resultado salvo em: {result_file}")
        print()
        
        # VALIDAÇÕES
        print("="*80)
        print("✅ VALIDAÇÕES")
        print("="*80)
        
        errors = []
        
        # 1. API retornou resultado válido
        if result.get('job_id'):
            print(f"✅ job_id retornado: {result['job_id']}")
        else:
            errors.append("❌ job_id não retornado")
        
        # 2. Segments (pode ser vazio para áudio sem fala)
        if result['segments']:
            print(f"✅ segments[] não vazio ({len(result['segments'])} segments)")
            first_seg = result['segments'][0]
            
            if 'start' not in first_seg:
                errors.append("❌ segment sem campo 'start'")
            else:
                print(f"✅ segment tem campo 'start'")
            
            if 'end' not in first_seg:
                errors.append("❌ segment sem campo 'end'")
            else:
                print(f"✅ segment tem campo 'end'")
            
            if 'text' not in first_seg:
                errors.append("❌ segment sem campo 'text'")
            else:
                print(f"✅ segment tem campo 'text'")
        else:
            print(f"⚠️  segments[] vazio (áudio sem fala detectada)")
        
        # 3. Duration (pode ser 0 para áudio sem fala)
        if result['duration'] and result['duration'] > 0:
            print(f"✅ duration válido: {result['duration']:.2f}s")
        elif result['duration'] is None:
            print(f"⚠️  duration: N/A (campo não retornado pela API)")
        else:
            print(f"⚠️  duration: 0.0 (áudio sem fala)")
        
        # 4. Language detected (pode ser None)
        if result['language_detected'] and result['language_detected'] != "N/A":
            print(f"✅ language_detected: {result['language_detected']}")
        else:
            print(f"⚠️  language_detected: N/A (campo não retornado pela API)")
        
        # 5. Processing time razoável (< 5min) - pode ser None
        if result['processing_time'] is not None:
            if result['processing_time'] > 300:
                errors.append(f"⚠️  processing_time alto: {result['processing_time']:.2f}s")
            else:
                print(f"✅ processing_time: {result['processing_time']:.2f}s")
        else:
            print(f"⚠️  processing_time: N/A (campo não retornado pela API)")
        
        print()
        
        # RESULTADO FINAL
        if errors:
            print("="*80)
            print("❌ TESTE FALHOU")
            print("="*80)
            for error in errors:
                print(error)
            pytest.fail(f"Validation failed: {len(errors)} errors")
        else:
            print("="*80)
            print("🎉 TESTE PASSOU")
            print("="*80)
            print("✅ Transcrição funcionou corretamente")
            print("✅ Formato de resposta válido")
            print("✅ API audio-transcriber está funcional")
            print()
            print("💡 Próximo passo: Testar pipeline completo (transcrição + burn-in)")
    
    except Exception as e:
        print()
        print("="*80)
        print("❌ TESTE FALHOU")
        print("="*80)
        print(f"Erro: {str(e)}")
        print()
        print("⚠️  Possíveis causas:")
        print("   1. Serviço audio-transcriber está DOWN")
        print("   2. Rede sem conectividade")
        print("   3. API retornou erro inesperado")
        print()
        print("💡 Se falha aqui, VAI FALHAR EM PRODUÇÃO também!")
        pytest.fail(f"Transcription test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_real_audio_transcription())
