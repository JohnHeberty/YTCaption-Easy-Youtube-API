# SPRINT-03: Arquitetura e Testes End-to-End (P2)

**Duração:** 2 semanas (10 dias úteis)  
**Prioridade:** P2 (Melhorias Estruturais)  
**Story Points:** 21  
**Impacto Esperado:** +100% cobertura de testes, +50% manutenibilidade  
**Data de Criação:** 18/02/2026  
**Status:** 🟡 PENDENTE (aguarda Sprint-02)

---

## 📋 Objetivos da Sprint

Melhorar **arquitetura** e **qualidade do código** através de:
- Testes end-to-end do pipeline completo
- Refatoração de dependências hardcoded
- Snapshot testing para FFmpeg
- BDD com Cucumber/Behave para casos reais

### Métricas de Sucesso
- ✅ Cobertura de testes: 45% → 85% (+40pp)
- ✅ Testes E2E cobrindo 100% do happy path
- ✅ Regression testing automatizado
- ✅ Injeção de dependências completa

---

## 🎯 Riscos Corrigidos

Esta sprint corrige os seguintes riscos do Risk Register:

- **R-013:** Sem Testes End-to-End do Pipeline
- Refatoração de código hardcoded
- Automação de testes de regressão
- Documentação técnica

---

## 📝 Tasks Detalhadas

### Task 1: Testes End-to-End do Pipeline (R-013)

**Story Points:** 8  
**Prioridade:** P2  
**Impacto:** +50% confiança em deploys

#### Descrição
Implementar testes E2E que validam todo o pipeline: upload → processing → download.

#### Sub-tasks

##### 1.1: Setup de Fixtures Realistas

**Arquivo:** `tests/fixtures/samples.py` (NOVO)

```python
"""
Test fixtures with real sample data

Provides realistic audio/video samples for E2E testing.
"""
import os
from pathlib import Path
from typing import Dict
import httpx
import hashlib

# Diretório de fixtures
FIXTURES_DIR = Path(__file__).parent / 'data'
FIXTURES_DIR.mkdir(exist_ok=True)


class TestSamples:
    """Gerencia samples de teste"""
    
    # Audio samples
    AUDIO_30SEC_MP3 = {
        'filename': 'audio_30sec.mp3',
        'duration': 30.0,
        'format': 'mp3',
        'size_bytes': 480_000,  # ~480KB
        'url': 'https://example.com/samples/audio_30sec.mp3',  # Substituir por URL real
        'sha256': 'abc123...'  # Hash esperado
    }
    
    AUDIO_60SEC_WAV = {
        'filename': 'audio_60sec.wav',
        'duration': 60.0,
        'format': 'wav',
        'size_bytes': 10_560_000,  # ~10MB
        'url': 'https://example.com/samples/audio_60sec.wav',
        'sha256': 'def456...'
    }
    
    # Video samples (shorts)
    SHORT_10SEC_1080P = {
        'filename': 'short_10sec_1080p.mp4',
        'duration': 10.0,
        'resolution': '1080x1920',
        'fps': 30,
        'codec': 'h264',
        'url': 'https://example.com/samples/short_10sec_1080p.mp4',
        'sha256': 'ghi789...'
    }
    
    SHORT_15SEC_720P = {
        'filename': 'short_15sec_720p.mp4',
        'duration': 15.0,
        'resolution': '720x1280',
        'fps': 30,
        'codec': 'h264',
        'url': 'https://example.com/samples/short_15sec_720p.mp4',
        'sha256': 'jkl012...'
    }
    
    @staticmethod
    async def download_sample(sample: Dict) -> Path:
        """
        Download sample se não existir localmente
        
        Returns:
            Path do arquivo baixado
        """
        file_path = FIXTURES_DIR / sample['filename']
        
        # Se já existe, verificar hash
        if file_path.exists():
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            if file_hash == sample['sha256']:
                return file_path
        
        # Download
        async with httpx.AsyncClient() as client:
            response = await client.get(sample['url'])
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
        
        return file_path
    
    @staticmethod
    def generate_dummy_audio(duration: float = 30.0) -> Path:
        """
        Gera arquivo de áudio dummy com FFmpeg
        
        Útil se samples externos não estiverem disponíveis.
        """
        import subprocess
        
        filename = f'dummy_audio_{int(duration)}sec.mp3'
        file_path = FIXTURES_DIR / filename
        
        if file_path.exists():
            return file_path
        
        # Gerar tom de 440Hz (Lá)
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'sine=frequency=440:duration={duration}',
            '-ac', '2',
            '-ar', '44100',
            str(file_path)
        ], check=True, capture_output=True)
        
        return file_path
    
    @staticmethod
    def generate_dummy_video(duration: float = 10.0, resolution: str = '1080x1920') -> Path:
        """
        Gera vídeo dummy com FFmpeg
        
        Args:
            duration: Duração em segundos
            resolution: Resolução (WxH)
        
        Returns:
            Path do vídeo gerado
        """
        import subprocess
        
        w, h = resolution.split('x')
        filename = f'dummy_video_{int(duration)}sec_{resolution}.mp4'
        file_path = FIXTURES_DIR / filename
        
        if file_path.exists():
            return file_path
        
        # Gerar vídeo com cor sólida
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=blue:s={w}x{h}:d={duration}',
            '-f', 'lavfi',
            '-i', f'sine=frequency=440:duration={duration}',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-shortest',
            str(file_path)
        ], check=True, capture_output=True)
        
        return file_path
```

##### 1.2: Testes E2E com Mocks de APIs Externas

**Arquivo:** `tests/e2e/test_full_pipeline.py` (NOVO)

```python
"""
End-to-End Pipeline Tests

Tests complete flow: upload → process → download
"""
import pytest
import httpx
from pathlib import Path
from unittest.mock import patch, AsyncMock

from tests.fixtures.samples import TestSamples


@pytest.mark.asyncio
@pytest.mark.e2e
class TestFullPipeline:
    """Testes do pipeline completo"""
    
    @pytest.fixture
    async def api_client(self):
        """Cliente HTTP para API"""
        async with httpx.AsyncClient(
            base_url="http://localhost:8003",
            timeout=600.0  # 10min para processing
        ) as client:
            yield client
    
    @pytest.fixture
    async def sample_audio(self):
        """Áudio de teste"""
        return TestSamples.generate_dummy_audio(duration=30.0)
    
    @pytest.fixture
    async def sample_shorts(self):
        """Shorts de teste"""
        return [
            TestSamples.generate_dummy_video(duration=10.0),
            TestSamples.generate_dummy_video(duration=10.0),
            TestSamples.generate_dummy_video(duration=10.0),
        ]
    
    async def test_happy_path_full_pipeline(
        self,
        api_client,
        sample_audio,
        sample_shorts
    ):
        """
        Teste de sucesso completo:
        1. Upload de áudio
        2. Processing com mocks de APIs
        3. Download do vídeo final
        """
        # Mock APIs externas
        with patch('app.api.api_client.MicroservicesClient.search_shorts') as mock_search, \
             patch('app.api.api_client.MicroservicesClient.download_videos') as mock_download, \
             patch('app.api.api_client.MicroservicesClient.transcribe_audio') as mock_transcribe:
            
            # Setup mocks
            mock_search.return_value = [
                {'video_id': 'short1', 'url': 'https://yt.com/short1'},
                {'video_id': 'short2', 'url': 'https://yt.com/short2'},
                {'video_id': 'short3', 'url': 'https://yt.com/short3'},
            ]
            
            mock_download.return_value = {
                'short1': str(sample_shorts[0]),
                'short2': str(sample_shorts[1]),
                'short3': str(sample_shorts[2]),
            }
            
            mock_transcribe.return_value = {
                'segments': [
                    {'start': 0.0, 'end': 10.0, 'text': 'Segment 1'},
                    {'start': 10.0, 'end': 20.0, 'text': 'Segment 2'},
                    {'start': 20.0, 'end': 30.0, 'text': 'Segment 3'},
                ]
            }
            
            # 1. Upload de áudio
            with open(sample_audio, 'rb') as f:
                response = await api_client.post(
                    '/create',
                    files={'audio_file': ('audio.mp3', f, 'audio/mpeg')},
                    data={
                        'shorts_video_query': 'test shorts',
                        'max_shorts': 5,
                        'aspect_ratio': '9:16',
                        'crop_position': 'center'
                    }
                )
            
            assert response.status_code == 202
            job_data = response.json()
            job_id = job_data['job_id']
            
            print(f"✅ Job created: {job_id}")
            
            # 2. Polling de status até completo
            max_attempts = 60  # 10min com polling de 10s
            
            for attempt in range(max_attempts):
                response = await api_client.get(f'/jobs/{job_id}')
                assert response.status_code == 200
                
                status = response.json()
                print(f"📊 Status: {status['status']} - {status['progress']}%")
                
                if status['status'] == 'completed':
                    break
                
                if status['status'] == 'failed':
                    pytest.fail(f"Job failed: {status.get('error_message')}")
                
                await asyncio.sleep(10)
            else:
                pytest.fail(f"Job timed out after {max_attempts * 10}s")
            
            # 3. Download do vídeo final
            response = await api_client.get(f'/download/{job_id}')
            assert response.status_code == 200
            assert response.headers['content-type'] == 'video/mp4'
            
            # Salvar para inspeção manual
            output = Path('tests/outputs') / f'{job_id}_final.mp4'
            output.parent.mkdir(exist_ok=True)
            
            with open(output, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Video saved: {output}")
            
            # 4. Validar output
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                 str(output)],
                capture_output=True,
                text=True
            )
            
            duration = float(result.stdout.strip())
            assert 25 < duration < 35, f"Invalid duration: {duration}s"
            
            print(f"✅ Duration validated: {duration}s")
    
    async def test_invalid_audio_format(self, api_client):
        """Teste de validação: formato inválido"""
        # Upload de arquivo texto como áudio
        response = await api_client.post(
            '/create',
            files={'audio_file': ('fake.mp3', b'not an audio file', 'audio/mpeg')},
            data={'shorts_video_query': 'test'}
        )
        
        assert response.status_code == 400
        assert 'Invalid audio format' in response.text
    
    async def test_audio_too_large(self, api_client):
        """Teste de validação: arquivo muito grande"""
        # Gerar arquivo dummy de 60MB
        large_file = b'x' * (60 * 1024 * 1024)
        
        response = await api_client.post(
            '/create',
            files={'audio_file': ('large.mp3', large_file, 'audio/mpeg')},
            data={'shorts_video_query': 'test'}
        )
        
        assert response.status_code == 400
        assert 'too large' in response.text.lower()
    
    async def test_job_cancellation(self, api_client, sample_audio):
        """Teste de cancelamento de job"""
        # 1. Criar job
        with open(sample_audio, 'rb') as f:
            response = await api_client.post(
                '/create',
                files={'audio_file': ('audio.mp3', f, 'audio/mpeg')},
                data={'shorts_video_query': 'test'}
            )
        
        job_id = response.json()['job_id']
        
        # 2. Aguardar iniciar processing
        await asyncio.sleep(2)
        
        # 3. Cancelar
        response = await api_client.post(f'/jobs/{job_id}/cancel')
        assert response.status_code == 200
        
        # 4. Verificar status
        await asyncio.sleep(1)
        response = await api_client.get(f'/jobs/{job_id}')
        status = response.json()
        
        assert status['status'] in ['cancelled', 'cancelling']
    
    async def test_retry_on_transient_failure(self, api_client, sample_audio):
        """Teste de retry automático em falha transitória"""
        call_count = 0
        
        def mock_download_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # Falhar nas primeiras 2 tentativas
            if call_count <= 2:
                raise httpx.TimeoutException("Timeout")
            
            # Sucesso na 3ª
            return {'short1': '/tmp/short1.mp4'}
        
        with patch(
            'app.api.api_client.MicroservicesClient.download_videos',
            side_effect=mock_download_with_failure
        ):
            with open(sample_audio, 'rb') as f:
                response = await api_client.post(
                    '/create',
                    files={'audio_file': ('audio.mp3', f, 'audio/mpeg')},
                    data={'shorts_video_query': 'test', 'max_shorts': 1}
                )
            
            job_id = response.json()['job_id']
            
            # Aguardar processing
            for _ in range(30):
                response = await api_client.get(f'/jobs/{job_id}')
                status = response.json()
                
                if status['status'] in ['completed', 'failed']:
                    break
                
                await asyncio.sleep(5)
            
            # Verificar sucesso após retries
            assert status['status'] == 'completed'
            assert call_count == 3, f"Expected 3 calls (2 failures + 1 success), got {call_count}"
```

##### 1.3: Testes de Carga

**Arquivo:** `tests/load/test_concurrent_jobs.py` (NOVO)

```python
"""
Load tests for concurrent job processing
"""
import pytest
import asyncio
import httpx
from tests.fixtures.samples import TestSamples


@pytest.mark.asyncio
@pytest.mark.load
async def test_10_concurrent_jobs():
    """Processa 10 jobs concorrentes"""
    async with httpx.AsyncClient(base_url="http://localhost:8003", timeout=600.0) as client:
        sample_audio = TestSamples.generate_dummy_audio(duration=30.0)
        
        # Criar 10 jobs
        job_ids = []
        
        for i in range(10):
            with open(sample_audio, 'rb') as f:
                response = await client.post(
                    '/create',
                    files={'audio_file': (f'audio{i}.mp3', f, 'audio/mpeg')},
                    data={'shorts_video_query': f'test {i}', 'max_shorts': 3}
                )
            
            assert response.status_code == 202
            job_ids.append(response.json()['job_id'])
        
        print(f"✅ Created {len(job_ids)} jobs")
        
        # Polling paralelo
        async def wait_for_job(job_id):
            for _ in range(60):
                response = await client.get(f'/jobs/{job_id}')
                status = response.json()
                
                if status['status'] in ['completed', 'failed']:
                    return status
                
                await asyncio.sleep(10)
            
            return {'status': 'timeout'}
        
        results = await asyncio.gather(*[wait_for_job(jid) for jid in job_ids])
        
        # Verificar resultados
        completed = sum(1 for r in results if r['status'] == 'completed')
        failed = sum(1 for r in results if r['status'] == 'failed')
        timeout = sum(1 for r in results if r['status'] == 'timeout')
        
        print(f"📊 Results: {completed} completed, {failed} failed, {timeout} timeout")
        
        # Pelo menos 80% devem ter sucesso
        assert completed >= 8, f"Too many failures: {failed}"
```

**Critério de Aceite:**
- ✅ Teste E2E completo implementado
- ✅ Cobertura de happy path + error paths
- ✅ Testes de carga para 10 jobs concorrentes
- ✅ Todos os testes passando em CI

---

### Task 2: Snapshot Testing para FFmpeg (Regressão Visual)

**Story Points:** 5  
**Prioridade:** P2  
**Impacto:** +100% confiança em mudanças FFmpeg

#### Descrição
Implementar snapshot testing para detectar regressões visuais em outputs FFmpeg.

#### Sub-tasks

##### 2.1: Biblioteca de Snapshot

**Arquivo:** `tests/utils/snapshot_testing.py` (NOVO)

```python
"""
Snapshot testing for video/audio outputs

Compares generated outputs against golden snapshots.
"""
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional


class VideoSnapshot:
    """Gerencia snapshots de vídeos"""
    
    SNAPSHOTS_DIR = Path('tests/snapshots')
    
    @staticmethod
    def capture_video_metadata(video_path: Path) -> Dict:
        """
        Captura metadados do vídeo via ffprobe
        
        Returns:
            Dict com metadados estruturados
        """
        result = subprocess.run([
            'ffprobe',
            '-v', 'error',
            '-show_format',
            '-show_streams',
            '-print_format', 'json',
            str(video_path)
        ], capture_output=True, text=True, check=True)
        
        probe_data = json.loads(result.stdout)
        
        # Extrair campos relevantes
        video_stream = next(
            (s for s in probe_data['streams'] if s['codec_type'] == 'video'),
            None
        )
        audio_stream = next(
            (s for s in probe_data['streams'] if s['codec_type'] == 'audio'),
            None
        )
        
        metadata = {
            'duration': float(probe_data['format'].get('duration', 0)),
            'size_bytes': int(probe_data['format'].get('size', 0)),
            'bit_rate': int(probe_data['format'].get('bit_rate', 0)),
        }
        
        if video_stream:
            metadata['video'] = {
                'codec': video_stream.get('codec_name'),
                'width': video_stream.get('width'),
                'height': video_stream.get('height'),
                'fps': eval(video_stream.get('r_frame_rate', '0/1')),  # '30/1' → 30.0
                'pix_fmt': video_stream.get('pix_fmt'),
            }
        
        if audio_stream:
            metadata['audio'] = {
                'codec': audio_stream.get('codec_name'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': audio_stream.get('channels'),
            }
        
        return metadata
    
    @staticmethod
    def extract_frame_hashes(video_path: Path, num_frames: int = 10) -> list:
        """
        Extrai hashes de frames específicos para comparação
        
        Args:
            video_path: Path do vídeo
            num_frames: Número de frames a extrair (distribuídos uniformemente)
        
        Returns:
            Lista de hashes SHA256 dos frames
        """
        from app.infrastructure.subprocess_utils import run_subprocess_with_timeout
        
        # Obter duração
        metadata = VideoSnapshot.capture_video_metadata(video_path)
        duration = metadata['duration']
        
        # Calcular timestamps
        interval = duration / (num_frames + 1)
        timestamps = [interval * (i + 1) for i in range(num_frames)]
        
        hashes = []
        
        for i, ts in enumerate(timestamps):
            # Extrair frame
            output = Path(f'/tmp/frame_{i}.png')
            
            run_subprocess_with_timeout([
                'ffmpeg', '-y',
                '-ss', str(ts),
                '-i', str(video_path),
                '-vframes', '1',
                '-f', 'image2',
                str(output)
            ], timeout=10)
            
            # Calcular hash
            with open(output, 'rb') as f:
                frame_hash = hashlib.sha256(f.read()).hexdigest()
            
            hashes.append(frame_hash)
            output.unlink()
        
        return hashes
    
    @staticmethod
    def save_snapshot(name: str, video_path: Path):
        """
        Salva snapshot do vídeo
        
        Args:
            name: Nome do snapshot (ex: 'concat_3_shorts_center_crop')
            video_path: Path do vídeo gerado
        """
        VideoSnapshot.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        
        snapshot = {
            'metadata': VideoSnapshot.capture_video_metadata(video_path),
            'frame_hashes': VideoSnapshot.extract_frame_hashes(video_path, num_frames=5)
        }
        
        snapshot_file = VideoSnapshot.SNAPSHOTS_DIR / f'{name}.json'
        
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        print(f"✅ Snapshot saved: {snapshot_file}")
    
    @staticmethod
    def compare_snapshot(name: str, video_path: Path, tolerance: float = 0.05) -> bool:
        """
        Compara vídeo com snapshot salvo
        
        Args:
            name: Nome do snapshot
            video_path: Vídeo a comparar
            tolerance: Tolerância para diferenças (5% por padrão)
        
        Returns:
            True se match, False caso contrário
        
        Raises:
            FileNotFoundError: Se snapshot não existir
        """
        snapshot_file = VideoSnapshot.SNAPSHOTS_DIR / f'{name}.json'
        
        if not snapshot_file.exists():
            raise FileNotFoundError(
                f"Snapshot not found: {name}. "
                f"Run VideoSnapshot.save_snapshot('{name}', video_path) to create it."
            )
        
        # Carregar snapshot esperado
        with open(snapshot_file) as f:
            expected = json.load(f)
        
        # Capturar snapshot atual
        actual = {
            'metadata': VideoSnapshot.capture_video_metadata(video_path),
            'frame_hashes': VideoSnapshot.extract_frame_hashes(video_path, num_frames=5)
        }
        
        # Comparar metadados (com tolerância)
        def compare_with_tolerance(expected_val, actual_val, tol):
            if isinstance(expected_val, (int, float)):
                diff = abs(expected_val - actual_val) / max(expected_val, 1)
                return diff <= tol
            return expected_val == actual_val
        
        errors = []
        
        # Duration
        if not compare_with_tolerance(
            expected['metadata']['duration'],
            actual['metadata']['duration'],
            tolerance
        ):
            errors.append(
                f"Duration mismatch: expected {expected['metadata']['duration']}s, "
                f"got {actual['metadata']['duration']}s"
            )
        
        # Resolution
        if expected['metadata'].get('video'):
            exp_w = expected['metadata']['video']['width']
            act_w = actual['metadata']['video']['width']
            
            if exp_w != act_w:
                errors.append(f"Width mismatch: expected {exp_w}, got {act_w}")
        
        # Frame hashes (devem ser idênticos para 80% dos frames)
        matching_frames = sum(
            1 for e, a in zip(expected['frame_hashes'], actual['frame_hashes'])
            if e == a
        )
        
        match_rate = matching_frames / len(expected['frame_hashes'])
        
        if match_rate < 0.8:
            errors.append(
                f"Frame hashes mismatch: only {match_rate:.0%} frames match "
                f"(expected 80%+)"
            )
        
        if errors:
            print(f"❌ Snapshot comparison failed for '{name}':")
            for error in errors:
                print(f"  - {error}")
            return False
        
        print(f"✅ Snapshot comparison passed for '{name}'")
        return True
```

##### 2.2: Testes com Snapshots

**Arquivo:** `tests/snapshot/test_ffmpeg_outputs.py` (NOVO)

```python
"""
Snapshot tests for FFmpeg operations
"""
import pytest
from pathlib import Path
from tests.fixtures.samples import TestSamples
from tests.utils.snapshot_testing import VideoSnapshot
from app.services.video_builder import VideoBuilder


@pytest.mark.snapshot
class TestFFmpegSnapshots:
    """Testes de regressão com snapshots"""
    
    @pytest.fixture
    def video_builder(self):
        return VideoBuilder()
    
    async def test_concat_3_shorts_center_crop(self, video_builder):
        """Snapshot de concatenação c/ crop center"""
        # Gerar inputs
        shorts = [
            TestSamples.generate_dummy_video(duration=10.0),
            TestSamples.generate_dummy_video(duration=10.0),
            TestSamples.generate_dummy_video(duration=10.0),
        ]
        
        output = Path('/tmp/concat_center.mp4')
        
        # Processar
        await video_builder.concat_videos(
            video_paths=[str(s) for s in shorts],
            output_path=str(output),
            aspect_ratio='9:16',
            crop_position='center'
        )
        
        # Comparar com snapshot
        assert VideoSnapshot.compare_snapshot('concat_3_shorts_center_crop', output)
    
    async def test_overlay_subtitles(self, video_builder):
        """Snapshot de overlay de legendas"""
        video = TestSamples.generate_dummy_video(duration=30.0)
        
        subtitles = [
            {'start': 0.0, 'end': 10.0, 'text': 'Segment 1'},
            {'start': 10.0, 'end': 20.0, 'text': 'Segment 2'},
            {'start': 20.0, 'end': 30.0, 'text': 'Segment 3'},
        ]
        
        output = Path('/tmp/overlay.mp4')
        
        await video_builder.overlay_subtitles(
            video_path=str(video),
            subtitles=subtitles,
            output_path=str(output)
        )
        
        assert VideoSnapshot.compare_snapshot('overlay_subtitles', output)
```

**Comando para criar snapshots:**

```bash
# Criar snapshots iniciais (golden)
pytest tests/snapshot/ --create-snapshots

# Rodar testes de regressão
pytest tests/snapshot/ -v
```

**Critério de Aceite:**
- ✅ Snapshot testing implementado
- ✅ Detecta mudanças visuais automati camente
- ✅ Integrado no CI

---

### Task 3: BDD com Behave (Casos de Negócio)

**Story Points:** 5  
**Prioridade:** P2  
**Impacto:** +50% clareza de requisitos

#### Descrição
Implementar testes BDD (Behavior-Driven Development) com Gherkin para casos de negócio.

#### Sub-tasks

##### 3.1: Setup Behave

**Instalar:**
```bash
pip install behave pytest-bdd
```

**Arquivo:** `features/make_video.feature` (NOVO)

```gherkin
# language: pt
Funcionalidade: Criação de Vídeo com Shorts

  Como usuário do serviço
  Eu quero enviar um áudio e obter um vídeo com shorts e legendas
  Para publicar conteúdo no formato vertical

  Cenário: Upload bem-sucedido de áudio
    Dado que eu tenho um arquivo de áudio válido
    Quando eu faço upload do arquivo
    Então o job é criado com sucesso
    E eu recebo um job_id
    E o status inicial é "processing"

  Cenário: Processamento completo com 5 shorts
    Dado que eu criei um job com 5 shorts
    Quando o processing termina
    Então o vídeo final tem duração próxima ao áudio original
    E o vídeo contém legendas sincronizadas
    E o aspect ratio é 9:16

  Cenário: Validação de formato de áudio inválido
    Dado que eu tenho um arquivo de texto
    Quando eu tento fazer upload como áudio
    Então eu recebo erro 400
    E a mensagem contém "Invalid audio format"

  Cenário: Validação de tamanho máximo
    Dado que eu tenho um arquivo de 60MB
    Quando eu tento fazer upload
    Então eu recebo erro 400
    E a mensagem contém "too large"

  Cenário: Retry automático em falha de API
    Dado que a API de download está instável
    Quando o job processa
    Então o sistema faz retry automático
    E o job completa com sucesso após 3 tentativas

  Cenário: Circuit breaker em API indisponível
    Dado que a API de busca está totalmente fora
    Quando múltiplos jobs tentam usar a API
    Então o circuit breaker abre
    E os jobs falham rapidamente
    E nenhum job fica em retry infinito
```

##### 3.2: Step Definitions

**Arquivo:** `features/steps/make_video_steps.py` (NOVO)

```python
"""
Step definitions for make-video BDD tests
"""
from behave import given, when, then
import httpx
import asyncio
from pathlib import Path


@given('que eu tenho um arquivo de áudio válido')
def step_impl(context):
    from tests.fixtures.samples import TestSamples
    context.audio_file = TestSamples.generate_dummy_audio(duration=30.0)


@given('que eu tenho um arquivo de texto')
def step_impl(context):
    context.audio_file = Path('/tmp/fake_audio.txt')
    context.audio_file.write_text('This is not audio')


@given('que eu tenho um arquivo de 60MB')
def step_impl(context):
    context.audio_file = Path('/tmp/large_audio.bin')
    context.audio_file.write_bytes(b'x' * (60 * 1024 * 1024))


@when('eu faço upload do arquivo')
def step_impl(context):
    async def upload():
        async with httpx.AsyncClient(base_url="http://localhost:8003") as client:
            with open(context.audio_file, 'rb') as f:
                response = await client.post(
                    '/create',
                    files={'audio_file': ('audio.mp3', f, 'audio/mpeg')},
                    data={'shorts_video_query': 'test', 'max_shorts': 3}
                )
            context.response = response
    
    asyncio.run(upload())


@when('eu tento fazer upload como áudio')
def step_impl(context):
    async def upload():
        async with httpx.AsyncClient(base_url="http://localhost:8003") as client:
            with open(context.audio_file, 'rb') as f:
                response = await client.post(
                    '/create',
                    files={'audio_file': ('audio.mp3', f, 'audio/mpeg')},
                    data={'shorts_video_query': 'test'}
                )
            context.response = response
    
    asyncio.run(upload())


@then('o job é criado com sucesso')
def step_impl(context):
    assert context.response.status_code == 202


@then('eu recebo um job_id')
def step_impl(context):
    data = context.response.json()
    assert 'job_id' in data
    context.job_id = data['job_id']


@then('o status inicial é "{status}"')
def step_impl(context, status):
    data = context.response.json()
    assert data['status'] == status


@then('eu recebo erro 400')
def step_impl(context):
    assert context.response.status_code == 400


@then('a mensagem contém "{text}"')
def step_impl(context, text):
    assert text in context.response.text
```

**Rodar testes BDD:**
```bash
behave features/
```

**Critério de Aceite:**
- ✅ BDD implementado com Behave
- ✅ 10+ cenários de negócio cobertos
- ✅ Testes legíveis por não-técnicos

---

### Task 4: Injeção de Dependências (Refatoração)

**Story Points:** 3  
**Prioridade:** P2  
**Impacto:** +50% testabilidade

#### Descrição
Refatorar código hardcoded para usar injeção de dependências.

#### Sub-tasks

##### 4.1: Definir Interfaces

**Arquivo:** `app/interfaces/video_processor.py` (NOVO)

```python
"""
Interfaces for dependency injection
"""
from abc import ABC, abstractmethod
from typing import List, Dict


class IVideoProcessor(ABC):
    """Interface para processamento de vídeo"""
    
    @abstractmethod
    async def concat_videos(
        self,
        video_paths: List[str],
        output_path: str,
        aspect_ratio: str,
        crop_position: str
    ):
        pass
    
    @abstractmethod
    async def overlay_subtitles(
        self,
        video_path: str,
        subtitles: List[Dict],
        output_path: str
    ):
        pass


class IVideoDownloader(ABC):
    """Interface para download de vídeos"""
    
    @abstractmethod
    async def download_videos(
        self,
        video_ids: List[str]
    ) -> Dict[str, str]:
        pass


class IAudioTranscriber(ABC):
    """Interface para transcrição"""
    
    @abstractmethod
    async def transcribe(
        self,
        audio_path: str
    ) -> List[Dict]:
        pass
```

##### 4.2: Container de DI

**Arquivo:** `app/infrastructure/dependency_injection.py` (NOVO)

```python
"""
Dependency Injection Container
"""
from app.interfaces.video_processor import (
    IVideoProcessor,
    IVideoDownloader,
    IAudioTranscriber
)
from app.services.video_builder import VideoBuilder
from app.api.api_client import MicroservicesClient


class DIContainer:
    """Container de dependências"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._services = {}
        self._initialized = True
    
    def register(self, interface: type, implementation: type):
        """Registra implementação para interface"""
        self._services[interface] = implementation
    
    def resolve(self, interface: type):
        """Resolve interface para implementação"""
        implementation = self._services.get(interface)
        
        if implementation is None:
            raise ValueError(f"No implementation registered for {interface}")
        
        return implementation()
    
    @classmethod
    def setup_production(cls):
        """Setup para produção"""
        container = cls()
        
        container.register(IVideoProcessor, VideoBuilder)
        container.register(IVideoDownloader, MicroservicesClient)
        container.register(IAudioTranscriber, MicroservicesClient)
        
        return container
    
    @classmethod
    def setup_testing(cls, mocks: dict):
        """Setup para testes com mocks"""
        container = cls()
        
        for interface, mock in mocks.items():
            container.register(interface, lambda: mock)
        
        return container


# Global container
di_container = DIContainer()
```

##### 4.3: Usar DI em Services

**Antes (hardcoded):**
```python
async def process_make_video(job_id: str):
    builder = VideoBuilder()  # HARDCODED
    client = MicroservicesClient()  # HARDCODED
    ...
```

**Depois (DI):**
```python
from app.infrastructure.dependency_injection import di_container
from app.interfaces.video_processor import IVideoProcessor

async def process_make_video(job_id: str):
    builder = di_container.resolve(IVideoProcessor)
    ...
```

**Critério de Aceite:**
- ✅ Interfaces definidas
- ✅ DI container implementado
- ✅ Refatoração de 100% dos services
- ✅ Testes usando mocks via DI

---

## 🧪 Plano de Testes

### Testes E2E
```bash
pytest tests/e2e/ -v --tb=short
```

### Testes de Snapshot
```bash
pytest tests/snapshot/ -v
```

### Testes BDD
```bash
behave features/
```

### Testes de Carga
```bash
pytest tests/load/ -v -s
```

---

## 📊 Métricas de Validação

### Antes da Sprint
- Cobertura de testes: 45%
- Testes E2E: 0
- Snapshot testing: 0
- BDD: 0

### Após Sprint
- Cobertura de testes: 85% (+40pp)
- Testes E2E: 15+ cenários
- Snapshot testing: 10+ snapshots
- BDD: 10+ cenários Gherkin

---

## ✅ Definition of Done

- [ ] 4 tasks implementadas
- [ ] Testes E2E completos
- [ ] Snapshot testing funcional
- [ ] BDD com 10+ cenários
- [ ] DI refatorado
- [ ] Cobertura >85%
- [ ] CI/CD verde

---

**Sprint Final!** 🎉
