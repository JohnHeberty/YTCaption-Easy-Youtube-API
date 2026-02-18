# SPRINT: Quick Wins - Correções Críticas P0

**Duração:** 2-3 dias  
**Prioridade:** CRÍTICA (P0)  
**Impacto Esperado:** -70% dos crashes críticos  
**Data de Criação:** 18/02/2026  
**Status:** 🔴 NÃO INICIADO

---

## 📋 Objetivos da Sprint

Implementar as **5 correções mais críticas** que causam crashes e perda de dados em produção. Esta sprint foca em **estabilidade imediata** com as mudanças de maior ROI (Return on Investment).

### Métricas de Sucesso
- ✅ Redução de 70% nos crashes de workers Celery
- ✅ Zero processos órfãos FFmpeg após 24h de operação
- ✅ Zero disk leaks de arquivos temporários
- ✅ Nenhum job travado em retry infinito
- ✅ Max 500MB RAM por job (vídeos até 60s)

---

## 🎯 Riscos Corrigidos

Esta sprint corrige os seguintes riscos do Risk Register:

- **R-001:** Subprocess FFmpeg sem Timeout Adequado
- **R-002:** API de Transcrição com Retry Infinito Perigoso
- **R-003:** Tempfiles Não Limpos em Exceções
- **R-004:** Falta de Cancelamento de Subprocessos em Timeout
- **R-005:** Validação OCR 100% Frames Sem Backpressure

---

## 📝 Tasks Detalhadas

### Task 1: Adicionar Timeout em Subprocess FFmpeg (R-001)

**Estimativa:** 4 horas  
**Prioridade:** P0  
**Impacto:** -60% crashes FFmpeg

#### Descrição
Implementar timeout com kill garantido em todas as chamadas `asyncio.create_subprocess_exec` para FFmpeg.

#### Sub-tasks

##### 1.1: Criar Wrapper Genérico para Subprocess com Timeout
**Arquivo:** `app/utils/subprocess_utils.py` (NOVO)

```python
"""
Subprocess utilities with timeout and cleanup
"""
import asyncio
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SubprocessTimeoutError(Exception):
    """Raised when subprocess exceeds timeout"""
    pass


async def run_subprocess_with_timeout(
    cmd: List[str],
    timeout: float,
    description: str = "subprocess",
    kill_timeout: float = 5.0
) -> Tuple[bytes, bytes, int]:
    """
    Execute subprocess com timeout e kill garantido.
    
    Args:
        cmd: Comando a executar (lista)
        timeout: Timeout em segundos
        description: Descrição para logs
        kill_timeout: Tempo para aguardar após SIGKILL
    
    Returns:
        (stdout, stderr, returncode)
    
    Raises:
        SubprocessTimeoutError: Se timeout excedido
    """
    proc = None
    try:
        logger.debug(f"Starting {description}: {' '.join(cmd)}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            
            logger.debug(
                f"{description} completed: returncode={proc.returncode}, "
                f"duration={timeout:.1f}s"
            )
            
            return stdout, stderr, proc.returncode
            
        except asyncio.TimeoutError:
            logger.error(
                f"{description} timeout after {timeout}s, killing process..."
            )
            
            # Tentar SIGTERM primeiro
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=kill_timeout)
                logger.warning(f"{description} terminated (SIGTERM)")
            except asyncio.TimeoutError:
                # SIGTERM não funcionou, forçar SIGKILL
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=kill_timeout)
                    logger.warning(f"{description} killed (SIGKILL)")
                except asyncio.TimeoutError:
                    logger.critical(
                        f"{description} could not be killed! PID may be orphaned"
                    )
            
            raise SubprocessTimeoutError(
                f"{description} exceeded timeout of {timeout}s"
            )
    
    finally:
        # Garantir que processo foi terminado
        if proc and proc.returncode is None:
            logger.warning(f"Cleanup: ensuring {description} is killed")
            try:
                proc.kill()
                await proc.wait()
            except Exception as e:
                logger.error(f"Failed to kill {description}: {e}")


async def run_ffmpeg_with_timeout(
    cmd: List[str],
    timeout: Optional[float] = None,
    base_timeout: float = 60,
    per_second_factor: float = 2.0,
    duration: Optional[float] = None
) -> Tuple[bytes, bytes]:
    """
    Execute FFmpeg com timeout calculado dinamicamente.
    
    Args:
        cmd: Comando FFmpeg
        timeout: Timeout fixo (se None, calcula baseado em duration)
        base_timeout: Timeout base (segundos)
        per_second_factor: Fator multiplicador por segundo de mídia
        duration: Duração estimada da mídia em segundos
    
    Returns:
        (stdout, stderr)
    
    Raises:
        SubprocessTimeoutError: Se timeout
        Exception: Se FFmpeg retornar erro
    """
    # Calcular timeout dinâmico
    if timeout is None:
        if duration:
            # Timeout = base + (duration * factor)
            # Ex: vídeo 60s → 60 + (60 * 2) = 180s timeout
            timeout = base_timeout + (duration * per_second_factor)
        else:
            timeout = base_timeout
    
    logger.info(f"Running FFmpeg with timeout={timeout:.1f}s")
    
    stdout, stderr, returncode = await run_subprocess_with_timeout(
        cmd=cmd,
        timeout=timeout,
        description="FFmpeg"
    )
    
    if returncode != 0:
        error_msg = stderr.decode('utf-8', errors='replace')
        raise Exception(f"FFmpeg failed (code {returncode}): {error_msg}")
    
    return stdout, stderr
```

**Critério de Aceite:**
- ✅ Wrapper implementado com testes unitários
- ✅ Timeout padrão de 60s + dinâmico baseado em duração
- ✅ Kill garantido (SIGTERM → SIGKILL)
- ✅ Logs estruturados com duração e returncode

---

##### 1.2: Aplicar Wrapper em video_builder.py

**Arquivo:** `app/services/video_builder.py`

**Mudanças necessárias:**

1. **Método `convert_to_h264` (linha ~75)**
```python
# ANTES (sem timeout):
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
stdout, stderr = await proc.communicate()

# DEPOIS (com timeout):
from app.utils.subprocess_utils import run_ffmpeg_with_timeout, SubprocessTimeoutError
from app.shared.exceptions import VideoProcessingException, ErrorCode

try:
    # Estimar duração do input
    input_info = await self.get_video_info(input_path)
    duration = input_info.get('duration', 60)
    
    stdout, stderr = await run_ffmpeg_with_timeout(
        cmd=cmd,
        duration=duration,
        base_timeout=60,
        per_second_factor=1.5  # H264 conversion é rápida
    )
except SubprocessTimeoutError as e:
    raise VideoProcessingException(
        f"H264 conversion timeout: {e}",
        ErrorCode.VIDEO_CONVERSION_TIMEOUT,
        details={"input": input_path, "timeout": str(e)}
    )
```

2. **Método `concatenate_videos` (linha ~236)**
```python
# Calcular duração total dos inputs
total_duration = sum([
    (await self.get_video_info(vf))['duration'] 
    for vf in video_files
])

stdout, stderr = await run_ffmpeg_with_timeout(
    cmd=cmd,
    duration=total_duration,
    base_timeout=120,  # Concat é mais lento
    per_second_factor=2.0
)
```

3. **Método `crop_video_permanent` (linha ~364)**
4. **Método `trim_video` (linha ~416)**
5. **Método `add_subtitles_to_video` (linha ~509)**
6. **Método `get_video_info` (linha ~588)**

**Arquivos adicionais a alterar:**
- `app/utils/audio_utils.py` (extract_audio, get_audio_duration)
- `app/services/subtitle_postprocessor.py` (subprocess.run → async wrapper)

**Critério de Aceite:**
- ✅ Todos os 7+ subprocess FFmpeg usando wrapper
- ✅ Timeout dinâmico baseado em duração de mídia
- ✅ Testes: vídeo 120s completa em <240s (não trava)
- ✅ Testes: vídeo corrompido mata processo em <60s

---

##### 1.3: Testes Automatizados

**Arquivo:** `tests/test_subprocess_utils.py` (NOVO)

```python
import pytest
import asyncio
from app.utils.subprocess_utils import run_subprocess_with_timeout, SubprocessTimeoutError


class TestSubprocessTimeout:
    
    @pytest.mark.asyncio
    async def test_normal_execution(self):
        """Comando normal deve executar com sucesso"""
        stdout, stderr, code = await run_subprocess_with_timeout(
            cmd=['echo', 'hello'],
            timeout=5.0,
            description="test-echo"
        )
        assert code == 0
        assert b'hello' in stdout
    
    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        """Timeout deve matar processo travado"""
        with pytest.raises(SubprocessTimeoutError, match="exceeded timeout"):
            await run_subprocess_with_timeout(
                cmd=['sleep', '60'],
                timeout=1.0,
                description="test-sleep"
            )
        
        # Verificar que processo foi morto
        await asyncio.sleep(1)
        # ps aux | grep sleep não deve mostrar processo
    
    @pytest.mark.asyncio
    async def test_ffmpeg_with_corrupted_video(self):
        """FFmpeg com vídeo corrompido deve falhar rápido"""
        import tempfile
        
        # Criar arquivo "vídeo" corrompido
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'not a video')
            corrupted = f.name
        
        try:
            from app.utils.subprocess_utils import run_ffmpeg_with_timeout
            
            with pytest.raises(Exception, match="FFmpeg failed"):
                await run_ffmpeg_with_timeout(
                    cmd=['ffmpeg', '-i', corrupted, '-c', 'copy', '/tmp/out.mp4'],
                    timeout=10
                )
        finally:
            os.unlink(corrupted)
```

**Critério de Aceite:**
- ✅ 100% cobertura do wrapper
- ✅ Teste de timeout força kill
- ✅ Teste com vídeo corrompido

---

### Task 2: Limitar Retry de Transcrição (R-002)

**Estimativa:** 2 horas  
**Prioridade:** P0  
**Impacto:** -40% deadlocks

#### Descrição
Adicionar limite de 10 tentativas no retry de transcrição de áudio, evitando loop infinito.

#### Sub-tasks

##### 2.1: Adicionar Constante de Configuração

**Arquivo:** `app/core/constants.py`

```python
class RetryLimits:
    """Limites de retry para operações externas"""
    
    # API externa de transcrição
    TRANSCRIPTION_MAX_ATTEMPTS = 10
    TRANSCRIPTION_BASE_BACKOFF = 5  # segundos
    TRANSCRIPTION_MAX_BACKOFF = 300  # 5 minutos
    
    # Download de vídeos
    DOWNLOAD_MAX_ATTEMPTS = 5
    DOWNLOAD_BASE_BACKOFF = 2
    DOWNLOAD_MAX_BACKOFF = 60
    
    # Busca de shorts
    SEARCH_MAX_ATTEMPTS = 3
    SEARCH_BASE_BACKOFF = 3
    SEARCH_MAX_BACKOFF = 30
```

##### 2.2: Refatorar Loop Infinito em celery_tasks.py

**Arquivo:** `app/infrastructure/celery_tasks.py` (linhas ~706-760)

```python
# ANTES (loop infinito):
segments = []
retry_attempt = 0
max_backoff = 300

while not segments:
    retry_attempt += 1
    try:
        segments = await api_client.transcribe_audio(...)
    except Exception:
        backoff_seconds = min(5 * (2 ** (retry_attempt - 1)), max_backoff)
        await asyncio.sleep(backoff_seconds)
        # ❌ CONTINUA TENTANDO PARA SEMPRE

# DEPOIS (com limite):
from app.core.constants import RetryLimits

segments = []
retry_attempt = 0

while retry_attempt < RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS:
    retry_attempt += 1
    
    try:
        logger.info(
            f"Transcription attempt {retry_attempt}/{RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS}",
            extra={
                "job_id": job_id,
                "attempt": retry_attempt,
                "max_attempts": RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS
            }
        )
        
        segments = await api_client.transcribe_audio(
            str(audio_path), 
            job.subtitle_language
        )
        
        if segments:
            logger.info(
                f"✅ Transcription succeeded on attempt {retry_attempt}",
                extra={
                    "job_id": job_id,
                    "segments_count": len(segments),
                    "attempt": retry_attempt
                }
            )
            break
    
    except MicroserviceException as e:
        # Verificar se atingiu limite
        if retry_attempt >= RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS:
            logger.error(
                f"❌ Transcription failed after {retry_attempt} attempts",
                extra={
                    "job_id": job_id,
                    "last_error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise AudioProcessingException(
                f"Transcription failed after {RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS} attempts",
                ErrorCode.TRANSCRIPTION_FAILED,
                details={
                    "attempts": retry_attempt,
                    "last_error": str(e),
                    "error_type": type(e).__name__
                }
            )
        
        # Calcular backoff exponencial
        backoff_seconds = min(
            RetryLimits.TRANSCRIPTION_BASE_BACKOFF * (2 ** (retry_attempt - 1)),
            RetryLimits.TRANSCRIPTION_MAX_BACKOFF
        )
        
        logger.warning(
            f"⚠️ Transcription attempt {retry_attempt} failed, retrying in {backoff_seconds}s",
            extra={
                "job_id": job_id,
                "attempt": retry_attempt,
                "retry_in": backoff_seconds,
                "error": str(e)
            }
        )
        
        # Atualizar job status
        await update_job_status(
            job_id,
            JobStatus.GENERATING_SUBTITLES,
            progress=80.0,
            stage_updates={
                "generating_subtitles": {
                    "status": "waiting_retry",
                    "metadata": {
                        "retry_attempt": retry_attempt,
                        "max_attempts": RetryLimits.TRANSCRIPTION_MAX_ATTEMPTS,
                        "retry_in_seconds": backoff_seconds,
                        "error": str(e)
                    }
                }
            }
        )
        
        await asyncio.sleep(backoff_seconds)

# Se saiu do loop sem segments, falhou
if not segments:
    raise AudioProcessingException(
        "No segments returned from transcription",
        ErrorCode.TRANSCRIPTION_FAILED
    )
```

**Critério de Aceite:**
- ✅ Loop limitado a 10 tentativas
- ✅ Backoff exponencial com jitter (opcional)
- ✅ Job status atualizado a cada retry
- ✅ Erro claro após limite excedido

##### 2.3: Testes

**Arquivo:** `tests/test_transcription_retry.py` (NOVO)

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.infrastructure.celery_tasks import process_make_video
from app.shared.exceptions import AudioProcessingException


class TestTranscriptionRetry:
    
    @pytest.mark.asyncio
    async def test_transcription_succeeds_on_retry(self, redis_store):
        """retry deve funcionar quando API volta"""
        # Mock: falha 2x depois sucesso
        call_count = 0
        
        async def mock_transcribe(audio_path, language):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("API temporarily down")
            return [{"start": 0, "end": 1, "text": "test"}]
        
        with patch('app.api.api_client.transcribe_audio', mock_transcribe):
            job_id = await create_test_job()
            await process_make_video(job_id)
            
            assert call_count == 3  # 2 falhas + 1 sucesso
    
    @pytest.mark.asyncio
    async def test_transcription_fails_after_max_retries(self):
        """retry deve falhar após 10 tentativas"""
        # Mock: sempre falha
        async def mock_transcribe_always_fails(audio_path, language):
            raise Exception("API permanently down")
        
        with patch('app.api.api_client.transcribe_audio', mock_transcribe_always_fails):
            job_id = await create_test_job()
            
            with pytest.raises(AudioProcessingException, match="failed after 10 attempts"):
                await process_make_video(job_id)
    
    @pytest.mark.asyncio
    async def test_transcription_retry_backoff(self):
        """Backoff exponencial deve crescer"""
        import time
        
        call_times = []
        
        async def mock_transcribe_track_time(audio_path, language):
            call_times.append(time.time())
            raise Exception("API down")
        
        with patch('app.api.api_client.transcribe_audio', mock_transcribe_track_time):
            try:
                await process_make_video(job_id)
            except:
                pass
        
        # Verificar intervalos crescentes
        intervals = [call_times[i+1] - call_times[i] for i in range(len(call_times)-1)]
        
        # Primeira tentativa: ~5s, segunda: ~10s, terceira: ~20s
        assert intervals[0] >= 4  # ~5s backoff
        assert intervals[1] >= 9  # ~10s backoff
        assert intervals[2] >= 19 # ~20s backoff
```

**Critério de Aceite:**
- ✅ Job falha após 10 tentativas (não infinito)
- ✅ Backoff exponencial verificado
- ✅ Status atualizado corretamente

---

### Task 3: Context Manager para Tempfiles (R-003)

**Estimativa:** 3 horas  
**Prioridade:** P0  
**Impacto:** -30% disk leaks

#### Descrição
Criar context managers para garantir cleanup de arquivos temporários mesmo em exceções.

#### Sub-tasks

##### 3.1: Criar Utilitários de Tempfile

**Arquivo:** `app/utils/tempfile_utils.py` (NOVO)

```python
"""
Safe temporary file utilities with guaranteed cleanup
"""
import os
import tempfile
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


@contextmanager
def temp_file(suffix: str = '', prefix: str = 'makevideo_', dir: Optional[str] = None):
    """
    Context manager para arquivo temporário com cleanup garantido.
    
    Uso:
        with temp_file(suffix='.wav') as path:
            subprocess.run(['ffmpeg', '-i', 'input.mp4', path])
            return path  # Arquivo é deletado ao sair do context
    
    Args:
        suffix: Sufixo do arquivo (ex: '.wav', '.mp4')
        prefix: Prefixo do arquivo
        dir: Diretório para criar arquivo (None = /tmp)
    
    Yields:
        str: Path do arquivo temporário
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
    os.close(fd)  # Fechar FD imediatamente
    
    try:
        logger.debug(f"Created temp file: {path}")
        yield path
    finally:
        try:
            if os.path.exists(path):
                os.unlink(path)
                logger.debug(f"Cleaned temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {path}: {e}")


@contextmanager
def temp_dir(suffix: str = '', prefix: str = 'makevideo_'):
    """
    Context manager para diretório temporário com cleanup garantido.
    
    Uso:
        with temp_dir() as dirpath:
            # Criar arquivos em dirpath
            ...
        # Diretório e conteúdo deletados automaticamente
    
    Args:
        suffix: Sufixo do diretório
        prefix: Prefixo do diretório
    
    Yields:
        str: Path do diretório temporário
    """
    import shutil
    
    dirpath = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
    
    try:
        logger.debug(f"Created temp dir: {dirpath}")
        yield dirpath
    finally:
        try:
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)
                logger.debug(f"Cleaned temp dir: {dirpath}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {dirpath}: {e}")


class TempFileManager:
    """
    Gerenciador de arquivos temporários com rastreamento.
    
    Útil para debugging e garantir cleanup mesmo após crashes.
    """
    
    def __init__(self):
        self.files = set()
        self.dirs = set()
    
    @contextmanager
    def temp_file(self, suffix='', prefix='makevideo_'):
        """Context manager com rastreamento"""
        with temp_file(suffix=suffix, prefix=prefix) as path:
            self.files.add(path)
            try:
                yield path
            finally:
                self.files.discard(path)
    
    def cleanup_all(self):
        """Limpa todos os temporários rastreados"""
        import shutil
        
        cleaned = 0
        failed = 0
        
        for path in list(self.files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup {path}: {e}")
                failed += 1
        
        for dirpath in list(self.dirs):
            try:
                if os.path.exists(dirpath):
                    shutil.rmtree(dirpath)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup {dirpath}: {e}")
                failed += 1
        
        self.files.clear()
        self.dirs.clear()
        
        logger.info(f"Cleanup: {cleaned} removed, {failed} failed")
        return cleaned, failed
```

##### 3.2: Refatorar audio_utils.py

**Arquivo:** `app/utils/audio_utils.py`

```python
# ANTES (leak possível):
def extract_audio(video_path, output_path=None, ...):
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
    
    try:
        subprocess.run(['ffmpeg', ...], check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        if os.path.exists(output_path):
            os.unlink(output_path)
        raise

# DEPOIS (cleanup garantido):
from app.utils.tempfile_utils import temp_file

async def extract_audio(
    video_path: str, 
    output_path: Optional[str] = None,
    sample_rate: int = 16000,
    timeout: int = 30
) -> str:
    """
    Extrai áudio de vídeo.
    
    Se output_path=None, cria arquivo temporário que será
    gerenciado pelo caller (usar context manager).
    """
    from app.utils.subprocess_utils import run_ffmpeg_with_timeout
    
    # Se output path fornecido, usar diretamente
    if output_path:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-i', video_path,
               '-vn', '-ar', str(sample_rate), '-ac', '1', '-y', output_path]
        
        await run_ffmpeg_with_timeout(cmd, timeout=timeout)
        return output_path
    
    # Senão, criar temp file (caller gerencia)
    with temp_file(suffix='.wav') as temp_audio:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-i', video_path,
               '-vn', '-ar', str(sample_rate), '-ac', '1', '-y', temp_audio]
        
        await run_ffmpeg_with_timeout(cmd, timeout=timeout)
        
        # Copiar para path persistente se necessário
        # ou retornar temp (será deletado ao sair do context)
        return temp_audio
```

##### 3.3: Refatorar video_validator.py

**Arquivo:** `app/video_processing/video_validator.py` (linhas ~669, ~803)

Substituir todos os `tempfile.NamedTemporaryFile(delete=False)` por context managers.

**Critério de Aceite:**
- ✅ Todos os tempfile.mkstemp substituídos
- ✅ Teste: força exception durante FFmpeg → tempfile deletado
- ✅ Teste: disk usage não cresce após 100 jobs

---

### Task 4: Kill Garantido de Subprocess (R-004)

**Estimativa:** 1 hora  
**Prioridade:** P0  
**Impacto:** -20% processos órfãos

#### Descrição
Já implementado na Task 1 (wrapper subprocess). Esta task adiciona monitoramento.

#### Sub-tasks

##### 4.1: Adicionar Monitoramento de Processos Órfãos

**Arquivo:** `app/infrastructure/process_monitor.py` (NOVO)

```python
"""
Process monitoring for detecting orphan processes
"""
import psutil
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ProcessMonitor:
    """Monitor para detectar processos órfãos"""
    
    @staticmethod
    def get_ffmpeg_processes() -> List[Dict]:
        """Retorna lista de processos FFmpeg ativos"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                if 'ffmpeg' in proc.info['name'].lower():
                    processes.append({
                        'pid': proc.info['pid'],
                        'cmdline': ' '.join(proc.info['cmdline'] or []),
                        'age_seconds': time.time() - proc.info['create_time']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return processes
    
    @staticmethod
    def kill_orphan_ffmpeg(max_age_seconds: int = 600):
        """
        Mata processos FFmpeg órfãos (rodando >10min)
        
        Args:
            max_age_seconds: Idade máxima antes de considerar órfão
        
        Returns:
            Número de processos mortos
        """
        killed = 0
        
        for proc_info in ProcessMonitor.get_ffmpeg_processes():
            if proc_info['age_seconds'] > max_age_seconds:
                try:
                    proc = psutil.Process(proc_info['pid'])
                    proc.kill()
                    killed += 1
                    logger.warning(
                        f"Killed orphan FFmpeg process",
                        extra={
                            'pid': proc_info['pid'],
                            'age': proc_info['age_seconds'],
                            'cmdline': proc_info['cmdline']
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to kill PID {proc_info['pid']}: {e}")
        
        return killed
```

##### 4.2: Cronjob de Limpeza

**Arquivo:** `app/infrastructure/celery_config.py`

```python
from celery.schedules import crontab

# Adicionar beat schedule
celery_app.conf.beat_schedule = {
    'cleanup-orphan-processes': {
        'task': 'app.infrastructure.celery_tasks.cleanup_orphan_processes',
        'schedule': crontab(minute='*/10'),  # A cada 10 minutos
    },
}

# Task
@celery_app.task
def cleanup_orphan_processes():
    """Limpa processos órfãos periodicamente"""
    from app.infrastructure.process_monitor import ProcessMonitor
    
    killed = ProcessMonitor.kill_orphan_ffmpeg(max_age_seconds=600)
    
    if killed > 0:
        logger.warning(f"🧹 Cleaned {killed} orphan FFmpeg processes")
    
    return killed
```

**Critério de Aceite:**
- ✅ Cronjob roda a cada 10min
- ✅ Processos >10min são mortos
- ✅ Métricas de orphans exportadas

---

### Task 5: Limitar OCR a 300 Frames (R-005)

**Estimativa:** 2 horas  
**Prioridade:** P0  
**Impacto:** -50% OOM

#### Descrição
Adicionar limites configuráveis para processamento OCR, evitando OOM em vídeos longos.

#### Sub-tasks

##### 5.1: Adicionar Configuração de Limites

**Arquivo:** `app/core/constants.py`

```python
class OCRLimits:
    """Limites para processamento OCR"""
    
    # Máximo de frames a processar
    MAX_FRAMES = 300  # ~10s @ 30fps
    
    # Taxa de amostragem (fps)
    SAMPLE_FPS = 2  # Amostra 2 frames por segundo
    
    # Batch size para processar em lotes
    BATCH_SIZE = 50
    
    # Limite de memória por batch (MB)
    MAX_MEMORY_PER_BATCH_MB = 500
```

##### 5.2: Refatorar VideoValidator

**Arquivo:** `app/video_processing/video_validator.py`

```python
# ANTES (força bruta):
def __init__(self, min_confidence=0.15, frames_per_second=None, max_frames=None, ...):
    self.frames_per_second = None  # ❌ Processa TODOS
    self.max_frames = None  # ❌ Sem limite

# DEPOIS (com limites):
from app.core.constants import OCRLimits

def __init__(
    self, 
    min_confidence: float = 0.15,
    frames_per_second: Optional[int] = None,
    max_frames: Optional[int] = None,
    redis_store: Optional[Any] = None
):
    self.min_confidence = min_confidence
    
    # Aplicar defaults seguros
    self.frames_per_second = frames_per_second or OCRLimits.SAMPLE_FPS
    self.max_frames = max_frames or OCRLimits.MAX_FRAMES
    
    logger.info(
        f"VideoValidator initialized with limits",
        extra={
            'sample_fps': self.frames_per_second,
            'max_frames': self.max_frames,
            'min_confidence': self.min_confidence
        }
    )
```

##### 5.3: Implementar Processamento em Batches

```python
def _detect_with_trsd(self, video_path, timeout=60):
    """Detecção com batching e GC"""
    import gc
    
    # Determinar frames a processar (com limite)
    info = self.get_video_info(video_path)
    duration = info['duration']
    fps = info['fps']
    
    total_frames = int(duration * fps)
    sample_interval = max(1, int(fps / self.frames_per_second))
    
    # Limitar total de frames
    frame_indices = list(range(0, total_frames, sample_interval))
    if len(frame_indices) > self.max_frames:
        logger.warning(
            f"Video has {len(frame_indices)} sample frames, limiting to {self.max_frames}",
            extra={'video_path': video_path, 'total_frames': total_frames}
        )
        frame_indices = frame_indices[:self.max_frames]
    
    logger.info(f"Processing {len(frame_indices)} frames (of {total_frames} total)")
    
    # Processar em batches
    all_results = []
    
    for i in range(0, len(frame_indices), OCRLimits.BATCH_SIZE):
        batch_indices = frame_indices[i:i+OCRLimits.BATCH_SIZE]
        
        logger.debug(f"Processing batch {i//OCRLimits.BATCH_SIZE + 1}: frames {i}-{i+len(batch_indices)}")
        
        # Processar batch
        batch_results = self._process_frame_batch(video_path, batch_indices)
        all_results.extend(batch_results)
        
        # Forçar garbage collection entre batches
        del batch_results
        gc.collect()
    
    # Analisar resultados...
    return has_subtitles, confidence, reason, debug_info
```

**Critério de Aceite:**
- ✅ Máximo 300 frames processados
- ✅ Processamento em batches de 50
- ✅ GC forçado entre batches
- ✅ Vídeo 60s @ 30fps usa <500MB RAM

---

## 🧪 Plano de Testes da Sprint

### Testes Unitários
```bash
pytest tests/test_subprocess_utils.py -v
pytest tests/test_transcription_retry.py -v
pytest tests/test_tempfile_utils.py -v
pytest tests/test_ocr_limits.py -v
```

### Testes de Integração
```bash
# Cenário 1: Job completo sem crashes
pytest tests/integration/test_full_pipeline_resilient.py

# Cenário 2: FFmpeg timeout
pytest tests/integration/test_ffmpeg_timeout.py

# Cenário 3: Transcrição com retry
pytest tests/integration/test_transcription_retry.py
```

### Testes de Carga
```bash
# 10 jobs simultâneos por 1 hora
pytest tests/load/test_concurrent_jobs.py --duration=3600 --workers=10
```

### Testes de Caos
```bash
# Simular falhas de rede, disk full, OOM
pytest tests/chaos/test_failure_scenarios.py
```

---

## 📊 Métricas de Validação

### Antes da Sprint
- Crashes FFmpeg: ~15 por dia
- Jobs travados: ~5 por dia
- Disk leaks: +10GB por semana
- Processos órfãos: 20-50 por dia
- OOM errors: 3-5 por dia

### Após Sprint (Expectativa)
- Crashes FFmpeg: <2 por dia (-87%)
- Jobs travados: 0
- Disk leaks: 0
- Processos órfãos: <5 por dia (-90%)
- OOM errors: 0

---

## 🚀 Deployment

### Rollout Planejado
1. **Staging:** Testar por 24h
2. **Canary:** 10% de tráfego por 12h
3. **Full rollout:** Se métricas OK

### Rollback Plan
```bash
# Se crashes aumentarem:
git revert <commit-hash>
kubectl rollout undo deployment/make-video
```

### Monitoramento Pós-Deploy
- Dashboard Grafana: "Quick Wins - Sprint Metrics"
- Alertas: crash_rate > 5/hora → PagerDuty
- Logs: grep "SubprocessTimeoutError\|AudioProcessingException"

---

## ✅ Definition of Done

- [ ] Todas as 5 tasks implementadas
- [ ] 100% testes passando (unit + integration)
- [ ] Cobertura de código >80% nos novos arquivos
- [ ] Code review aprovado por 2+ engenheiros
- [ ] Documentação atualizada (README + docstrings)
- [ ] Deployed em staging e validado por 24h
- [ ] Métricas confirmam -70% crashes
- [ ] Zero processos órfãos detectados em 24h
- [ ] Zero disk leaks após 100 jobs

---

**Próxima Sprint:** SPRINT-RESILIENCE-01.md (Resiliência de Processos P1)
