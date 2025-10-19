"""
Serviço de preparação de chunks de áudio.
Divide o áudio em pedaços menores usando FFmpeg e salva em disco
ANTES de enviar aos workers para processamento paralelo.
"""
from pathlib import Path
from typing import List, Tuple
import subprocess
import asyncio

from loguru import logger

from src.domain.exceptions import TranscriptionError


class ChunkPreparationService:
    """
    Prepara chunks de áudio em pasta isolada ANTES de enviar aos workers.
    
    - Divide áudio em chunks de duração fixa
    - Usa FFmpeg para extrair cada chunk
    - Salva chunks como arquivos WAV separados
    - Retorna lista de caminhos dos chunks criados
    """
    
    def __init__(self, chunk_duration_seconds: int = 120):
        """
        Inicializa serviço de preparação de chunks.
        
        Args:
            chunk_duration_seconds: Duração de cada chunk em segundos (default: 120s = 2min)
        """
        self.chunk_duration = chunk_duration_seconds
        logger.info(f"Chunk preparation service initialized: chunk_duration={chunk_duration_seconds}s")
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Obtém duração do áudio em segundos usando FFprobe.
        
        Args:
            audio_path: Caminho do arquivo de áudio
            
        Returns:
            Duração em segundos
            
        Raises:
            TranscriptionError: Se FFprobe falhar
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path)
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            duration = float(result.stdout.strip())
            logger.info(f"Audio duration: {duration:.2f}s ({audio_path.name})")
            return duration
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or "Unknown FFprobe error"
            raise TranscriptionError(f"Failed to get audio duration: {error_msg}")
        except ValueError as e:
            raise TranscriptionError(f"Invalid duration value from FFprobe: {e}")
        except subprocess.TimeoutExpired:
            raise TranscriptionError("FFprobe timed out (>30s)")
    
    def _calculate_chunk_times(self, total_duration: float) -> List[Tuple[float, float]]:
        """
        Calcula intervalos (start, end) para cada chunk.
        
        Args:
            total_duration: Duração total do áudio em segundos
            
        Returns:
            Lista de tuplas (start_time, end_time) em segundos
        """
        chunks = []
        current_time = 0.0
        
        while current_time < total_duration:
            start = current_time
            end = min(current_time + self.chunk_duration, total_duration)
            chunks.append((start, end))
            current_time = end
        
        logger.info(f"Calculated {len(chunks)} chunks for {total_duration:.2f}s audio")
        return chunks
    
    async def _extract_chunk_async(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float
    ):
        """
        Extrai chunk de áudio usando FFmpeg (async).
        
        Args:
            input_path: Arquivo de áudio original
            output_path: Caminho de saída do chunk
            start: Tempo inicial em segundos
            end: Tempo final em segundos
            
        Raises:
            TranscriptionError: Se FFmpeg falhar
        """
        duration = end - start
        
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-ar", "16000",          # 16kHz sample rate (Whisper requirement)
            "-ac", "1",              # Mono
            "-c:a", "pcm_s16le",    # PCM 16-bit (WAV format)
            "-y",                    # Overwrite output
            "-loglevel", "error",
            str(output_path)
        ]
        
        logger.debug(f"Extracting chunk: {start:.1f}s-{end:.1f}s -> {output_path.name}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5 minutos timeout por chunk
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                raise TranscriptionError(
                    f"FFmpeg chunk extraction failed (chunk {start:.1f}s-{end:.1f}s): {error_msg}"
                )
            
            # Verificar se arquivo foi criado
            if not output_path.exists():
                raise TranscriptionError(f"Chunk file was not created: {output_path}")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.debug(f"Chunk extracted: {output_path.name} ({file_size_mb:.2f} MB)")
            
        except asyncio.TimeoutError:
            raise TranscriptionError(f"FFmpeg chunk extraction timed out (chunk {start:.1f}s-{end:.1f}s)")
        except Exception as e:
            if isinstance(e, TranscriptionError):
                raise
            raise TranscriptionError(f"Failed to extract chunk: {str(e)}")
    
    async def prepare_chunks(
        self,
        audio_path: Path,
        chunks_output_dir: Path
    ) -> List[Path]:
        """
        Divide áudio em chunks e salva em disco (operação principal).
        
        Args:
            audio_path: Caminho do arquivo de áudio original
            chunks_output_dir: Diretório onde chunks serão salvos
            
        Returns:
            Lista ordenada de Paths dos chunks criados
            
        Raises:
            TranscriptionError: Se preparação falhar
        """
        logger.info(f"[CHUNK PREP] Starting chunk preparation: {audio_path.name}")
        
        # 1. Verificar se arquivo existe
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")
        
        # 2. Criar diretório de chunks se não existir
        chunks_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Obter duração total
        total_duration = self._get_audio_duration(audio_path)
        
        # 4. Calcular intervalos dos chunks
        chunk_times = self._calculate_chunk_times(total_duration)
        
        # 5. Extrair chunks em paralelo (async)
        chunk_paths = []
        tasks = []
        
        for idx, (start, end) in enumerate(chunk_times):
            chunk_path = chunks_output_dir / f"chunk_{idx:03d}.wav"
            chunk_paths.append(chunk_path)
            
            # Criar task async para extrair chunk
            task = self._extract_chunk_async(
                audio_path,
                chunk_path,
                start,
                end
            )
            tasks.append(task)
        
        # Executar todas as extrações em paralelo
        logger.info(f"[CHUNK PREP] Extracting {len(tasks)} chunks in parallel...")
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"[CHUNK PREP] Failed to extract chunks: {e}")
            raise
        
        # 6. Verificar que todos os chunks foram criados
        missing_chunks = [p for p in chunk_paths if not p.exists()]
        if missing_chunks:
            raise TranscriptionError(
                f"Failed to create {len(missing_chunks)} chunks: {[p.name for p in missing_chunks]}"
            )
        
        total_size_mb = sum(p.stat().st_size for p in chunk_paths) / (1024 * 1024)
        
        logger.info(
            f"[CHUNK PREP] Successfully prepared {len(chunk_paths)} chunks "
            f"(total: {total_size_mb:.2f} MB) in {chunks_output_dir}"
        )
        
        return chunk_paths
    
    def estimate_chunk_count(self, duration_seconds: float) -> int:
        """
        Estima número de chunks para uma duração de áudio.
        
        Args:
            duration_seconds: Duração do áudio em segundos
            
        Returns:
            Número estimado de chunks
        """
        import math
        return math.ceil(duration_seconds / self.chunk_duration)
