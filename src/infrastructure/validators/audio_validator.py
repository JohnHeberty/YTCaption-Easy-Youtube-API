"""
Audio File Validator - Validação antecipada de arquivos de áudio.

Features:
- Validação de headers e formato
- Verificação de codec suportado
- Detecção de arquivos corrompidos
- Estimativa de tempo de processamento
- Rejeita arquivos inválidos ANTES do processamento
"""
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class AudioMetadata:
    """Metadados extraídos do arquivo de áudio."""
    
    duration_seconds: float
    format_name: str
    codec_name: str
    sample_rate: int
    channels: int
    bit_rate: Optional[int]
    file_size_bytes: int
    is_valid: bool
    validation_errors: List[str]
    
    @property
    def file_size_mb(self) -> float:
        """Retorna tamanho do arquivo em MB."""
        return self.file_size_bytes / (1024 * 1024)
    
    @property
    def duration_formatted(self) -> str:
        """Retorna duração formatada (HH:MM:SS)."""
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class AudioValidator:
    """
    Validador de arquivos de áudio/vídeo.
    
    Usa FFprobe para validação eficiente sem carregar arquivo completo.
    """
    
    # Codecs de áudio suportados pelo Whisper (via FFmpeg)
    SUPPORTED_AUDIO_CODECS = {
        'aac', 'mp3', 'opus', 'vorbis', 'flac', 'pcm_s16le', 
        'pcm_s24le', 'pcm_f32le', 'wav', 'alac', 'wmav2'
    }
    
    # Formatos de container suportados
    SUPPORTED_FORMATS = {
        'mp4', 'webm', 'mkv', 'avi', 'mov', 'flv', 'wmv',
        'mp3', 'aac', 'ogg', 'opus', 'flac', 'wav', 'm4a'
    }
    
    # Limites recomendados
    MAX_DURATION_HOURS = 10
    MIN_DURATION_SECONDS = 0.5
    MAX_FILE_SIZE_GB = 5
    MIN_SAMPLE_RATE = 8000
    MAX_SAMPLE_RATE = 48000
    
    def __init__(self):
        """Inicializa validador."""
        logger.info("Audio validator initialized")
    
    def validate_file(
        self,
        file_path: Path,
        strict: bool = False
    ) -> AudioMetadata:
        """
        Valida arquivo de áudio/vídeo completo.
        
        Args:
            file_path: Caminho do arquivo
            strict: Se True, aplica validações mais rigorosas
            
        Returns:
            AudioMetadata com resultado da validação
        """
        errors: List[str] = []
        
        # 1. Verificar se arquivo existe
        if not file_path.exists():
            return AudioMetadata(
                duration_seconds=0,
                format_name="unknown",
                codec_name="unknown",
                sample_rate=0,
                channels=0,
                bit_rate=None,
                file_size_bytes=0,
                is_valid=False,
                validation_errors=["File does not exist"]
            )
        
        # 2. Verificar extensão do arquivo
        extension = file_path.suffix.lstrip('.').lower()
        if strict and extension not in self.SUPPORTED_FORMATS:
            errors.append(f"Unsupported file extension: {extension}")
        
        # 3. Obter tamanho do arquivo
        try:
            file_size = file_path.stat().st_size
        except Exception as e:
            return AudioMetadata(
                duration_seconds=0,
                format_name="unknown",
                codec_name="unknown",
                sample_rate=0,
                channels=0,
                bit_rate=None,
                file_size_bytes=0,
                is_valid=False,
                validation_errors=[f"Cannot read file: {e}"]
            )
        
        # 4. Verificar tamanho do arquivo
        if file_size == 0:
            errors.append("File is empty (0 bytes)")
        
        if file_size > self.MAX_FILE_SIZE_GB * 1024 * 1024 * 1024:
            errors.append(
                f"File too large: {file_size / (1024**3):.2f}GB "
                f"(max: {self.MAX_FILE_SIZE_GB}GB)"
            )
        
        # 5. Extrair metadados com FFprobe
        try:
            metadata = self._extract_metadata_ffprobe(file_path)
        except Exception as e:
            return AudioMetadata(
                duration_seconds=0,
                format_name="unknown",
                codec_name="unknown",
                sample_rate=0,
                channels=0,
                bit_rate=None,
                file_size_bytes=file_size,
                is_valid=False,
                validation_errors=[f"FFprobe failed: {e}"]
            )
        
        # 6. Validar metadados extraídos
        duration = metadata.get('duration', 0)
        format_name = metadata.get('format', 'unknown')
        codec_name = metadata.get('codec', 'unknown')
        sample_rate = metadata.get('sample_rate', 0)
        channels = metadata.get('channels', 0)
        bit_rate = metadata.get('bit_rate')
        
        # Validar duração
        if duration < self.MIN_DURATION_SECONDS:
            errors.append(
                f"File too short: {duration:.2f}s (min: {self.MIN_DURATION_SECONDS}s)"
            )
        
        if duration > self.MAX_DURATION_HOURS * 3600:
            errors.append(
                f"File too long: {duration/3600:.2f}h (max: {self.MAX_DURATION_HOURS}h)"
            )
        
        # Validar codec
        if strict and codec_name not in self.SUPPORTED_AUDIO_CODECS:
            errors.append(f"Unsupported audio codec: {codec_name}")
        
        # Validar sample rate
        if sample_rate > 0:
            if sample_rate < self.MIN_SAMPLE_RATE:
                errors.append(
                    f"Sample rate too low: {sample_rate}Hz (min: {self.MIN_SAMPLE_RATE}Hz)"
                )
            
            if sample_rate > self.MAX_SAMPLE_RATE:
                logger.warning(
                    f"High sample rate detected: {sample_rate}Hz "
                    f"(will be downsampled to 16000Hz)"
                )
        
        # Validar canais
        if channels == 0:
            errors.append("No audio channels detected")
        
        is_valid = len(errors) == 0
        
        result = AudioMetadata(
            duration_seconds=duration,
            format_name=format_name,
            codec_name=codec_name,
            sample_rate=sample_rate,
            channels=channels,
            bit_rate=bit_rate,
            file_size_bytes=file_size,
            is_valid=is_valid,
            validation_errors=errors
        )
        
        if is_valid:
            logger.info(
                f"Audio validation SUCCESS: {file_path.name} "
                f"({result.duration_formatted}, {result.file_size_mb:.2f}MB, "
                f"{codec_name})"
            )
        else:
            logger.warning(
                f"Audio validation FAILED: {file_path.name} - "
                f"Errors: {errors}"
            )
        
        return result
    
    def _extract_metadata_ffprobe(self, file_path: Path) -> Dict:
        """
        Extrai metadados usando FFprobe.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Dict com metadados
            
        Raises:
            Exception: Se FFprobe falhar
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-select_streams', 'a:0',  # Primeiro stream de áudio
            str(file_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            data = json.loads(result.stdout)
            
            # Extrair informações do formato
            format_info = data.get('format', {})
            duration = float(format_info.get('duration', 0))
            format_name = format_info.get('format_name', 'unknown').split(',')[0]
            bit_rate = int(format_info.get('bit_rate', 0)) if format_info.get('bit_rate') else None
            
            # Extrair informações do stream de áudio
            streams = data.get('streams', [])
            
            if not streams:
                # Tentar extrair áudio de vídeo
                logger.warning(f"No audio stream found in {file_path.name}, checking all streams...")
                cmd_all = cmd.copy()
                cmd_all[8] = 'a'  # Remover filtro de stream específico
                result_all = subprocess.run(cmd_all, capture_output=True, text=True, check=True, timeout=30)
                data_all = json.loads(result_all.stdout)
                streams = data_all.get('streams', [])
            
            # Pegar primeiro stream de áudio
            audio_stream = streams[0] if streams else {}
            
            codec_name = audio_stream.get('codec_name', 'unknown')
            sample_rate = int(audio_stream.get('sample_rate', 0))
            channels = int(audio_stream.get('channels', 0))
            
            return {
                'duration': duration,
                'format': format_name,
                'codec': codec_name,
                'sample_rate': sample_rate,
                'channels': channels,
                'bit_rate': bit_rate
            }
        
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or "Unknown FFprobe error"
            raise Exception(f"FFprobe command failed: {error_msg}")
        
        except subprocess.TimeoutExpired:
            raise Exception("FFprobe timed out (>30s)")
        
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse FFprobe output: {e}")
        
        except Exception as e:
            raise Exception(f"Metadata extraction failed: {e}")
    
    def estimate_processing_time(
        self,
        metadata: AudioMetadata,
        model_name: str = "base",
        device: str = "cpu"
    ) -> Tuple[float, float]:
        """
        Estima tempo de processamento baseado em benchmarks.
        
        Args:
            metadata: Metadados do áudio
            model_name: Nome do modelo Whisper
            device: Dispositivo (cpu/cuda)
            
        Returns:
            Tupla (min_seconds, max_seconds) de tempo estimado
        """
        duration = metadata.duration_seconds
        
        # Fatores de processamento (segundos de áudio por segundo de processamento)
        # Baseado em benchmarks reais do Whisper
        processing_factors = {
            'tiny': {'cpu': 2.0, 'cuda': 10.0},
            'base': {'cpu': 1.5, 'cuda': 8.0},
            'small': {'cpu': 0.8, 'cuda': 5.0},
            'medium': {'cpu': 0.4, 'cuda': 3.0},
            'large': {'cpu': 0.2, 'cuda': 2.0},
            'turbo': {'cpu': 1.0, 'cuda': 6.0}
        }
        
        factor = processing_factors.get(model_name, {}).get(device, 1.0)
        
        # Tempo de processamento = duração do áudio / fator
        estimated_time = duration / factor
        
        # Adicionar overhead (conversão, I/O, etc) - ~10-20%
        overhead_factor = 1.15
        
        min_time = estimated_time * overhead_factor * 0.8  # -20% margem
        max_time = estimated_time * overhead_factor * 1.5  # +50% margem
        
        return (min_time, max_time)
    
    def check_corruption(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Verifica se arquivo está corrompido tentando decodificar início.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Tupla (is_corrupted, error_message)
        """
        cmd = [
            'ffmpeg',
            '-v', 'error',
            '-i', str(file_path),
            '-t', '5',  # Testar apenas primeiros 5 segundos
            '-f', 'null',
            '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                return (True, error_msg)
            
            return (False, None)
        
        except subprocess.TimeoutExpired:
            return (True, "Decoding timed out - possibly corrupted")
        
        except Exception as e:
            return (True, f"Corruption check failed: {e}")
