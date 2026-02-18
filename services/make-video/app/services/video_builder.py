"""
Video Builder

Responsável pela montagem de vídeos usando FFmpeg.
Implementa APENAS processamento de vídeo - NÃO baixa vídeos.
"""

import asyncio
import logging
import json
import shutil
from pathlib import Path
from typing import List, Dict, Tuple

# Use new exception hierarchy
from ..shared.exceptions_v2 import (
    VideoException,
    VideoCorruptedException,
    VideoEncodingException,
    VideoInvalidResolutionException,
    ConcatenationException,
    SubtitleGenerationException,
    AudioNotFoundException,
    AudioCorruptedException,
    FFmpegTimeoutException,
    FFmpegFailedException,
    FFprobeFailedException,
    SubprocessTimeoutException
)
from ..infrastructure.subprocess_utils import (
    run_ffmpeg_with_timeout,
    run_ffprobe
)

logger = logging.getLogger(__name__)


class VideoBuilder:
    """Construtor de vídeos usando FFmpeg"""
    
    def __init__(self, output_dir: str, 
                 video_codec: str = "libx264",
                 audio_codec: str = "aac",
                 preset: str = "fast",
                 crf: int = 23):
        self.output_dir = Path(output_dir)
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.preset = preset
        self.crf = crf
        
        # Criar diretório de output se não existir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎬 VideoBuilder initialized")
        logger.info(f"   ├─ Output dir: {self.output_dir}")
        logger.info(f"   ├─ Video codec: {self.video_codec}")
        logger.info(f"   ├─ Audio codec: {self.audio_codec}")
        logger.info(f"   ├─ Preset: {self.preset}")
        logger.info(f"   └─ CRF: {self.crf}")
    
    async def convert_to_h264(self, input_path: str, output_path: str) -> str:
        """
        Converte vídeo para H264 mantendo resolução e proporção originais
        
        Args:
            input_path: Path do vídeo original
            output_path: Path do vídeo H264 de saída
        
        Returns:
            Path do vídeo convertido
        
        Raises:
            FFmpegFailedException: Se conversão falhar
            FFmpegTimeoutException: Se operação exceder timeout
        """
        logger.info(f"🔄 Converting to H264: {Path(input_path).name}")
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", self.video_codec,
            "-preset", self.preset,
            "-crf", str(self.crf),
            "-c:a", "copy",  # Copy audio stream
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        try:
            # Use subprocess utils with 10min timeout for video conversion
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=600,  # 10 minutes for H264 conversion
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise FFmpegFailedException(
                    operation="H264 conversion",
                    stderr=error_msg,
                    returncode=returncode,
                    details={"input": input_path, "output": output_path}
                )
            
            logger.info(f"✅ H264 conversion complete: {output_path}")
            return output_path
            
        except SubprocessTimeoutException as e:
            logger.error(f"❌ H264 conversion timeout: {e}")
            raise FFmpegTimeoutException(
                operation="H264 conversion",
                timeout=600,
                details={"input": input_path, "output": output_path},
                cause=e
            )
        except Exception as e:
            logger.error(f"❌ H264 conversion error: {e}")
            raise
    
    async def concatenate_videos(self, 
                                 video_files: List[str], 
                                 output_path: str, 
                                 aspect_ratio: str = "9:16",
                                 crop_position: str = "center",
                                 remove_audio: bool = True) -> str:
        """Concatena múltiplos vídeos aplicando crop para aspect ratio
        
        Args:
            video_files: Lista de caminhos dos vídeos para concatenar
            output_path: Caminho do vídeo de saída
            aspect_ratio: Proporção desejada (9:16, 16:9, 1:1, 4:5)
            crop_position: Posição do crop (center, top, bottom)
            remove_audio: Se True, remove áudio do vídeo final
        
        Returns:
            Caminho do vídeo gerado
        
        Raises:
            ConcatenationException: Se falhar a concatenação ou duração divergir
            FFmpegFailedException: Se FFmpeg falhar
            FFmpegTimeoutException: Se concatenação exceder 30min
        """
        
        logger.info(f"🎬 Concatenating {len(video_files)} videos")
        logger.info(f"   ├─ Aspect ratio: {aspect_ratio}")
        logger.info(f"   ├─ Crop position: {crop_position}")
        logger.info(f"   └─ Remove audio: {remove_audio}")
        
        # ✅ VALIDAR COMPATIBILIDADE (R-009: Video Compatibility Check)
        # Detecta incompatibilidades (codec, FPS, resolução) ANTES de concatenar
        logger.info(f"🔍 Validating video compatibility before concatenation...")
        
        from ..services.video_compatibility_validator import VideoCompatibilityValidator
        
        try:
            compat_result = await VideoCompatibilityValidator.validate_concat_compatibility(
                video_files=video_files,
                video_builder=self,
                strict=True,  # Fail if incompatible
                fps_tolerance=0.1
            )
            
            logger.info(
                f"✅ Compatibility check passed: all {compat_result['total_videos']} videos compatible",
                extra={
                    "reference_codec": compat_result['reference_video']['codec'] if compat_result['reference_video'] else None,
                    "reference_fps": compat_result['reference_video']['fps'] if compat_result['reference_video'] else None,
                    "reference_resolution": compat_result['reference_video']['resolution'] if compat_result['reference_video'] else None
                }
            )
        
        except Exception as compat_error:
            # Compatibility check failed - log and re-raise
            logger.error(
                f"❌ Video compatibility check failed: {compat_error}",
                exc_info=True
            )
            raise  # Re-raise to prevent concatenation of incompatible videos
        
        # Mapear aspect ratios para resoluções
        aspect_map = {
            "9:16": (1080, 1920),   # Vertical (Shorts, Stories)
            "16:9": (1920, 1080),   # Horizontal (YouTube padrão)
            "1:1": (1080, 1080),    # Quadrado (Instagram)
            "4:5": (1080, 1350),    # Instagram Feed
        }
        
        if aspect_ratio not in aspect_map:
            raise VideoInvalidResolutionException(
                aspect_ratio=aspect_ratio,
                valid_ratios=list(aspect_map.keys())
            )
        
        target_width, target_height = aspect_map[aspect_ratio]
        
        # Calcular crop filter baseado na posição
        # IMPORTANTE: scale aumenta o vídeo para cobrir o target, depois crop corta o excesso
        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase"
        
        if crop_position == "center":
            # Auto-center crop (padrão FFmpeg)
            crop_filter = f"crop={target_width}:{target_height}"
        elif crop_position == "top":
            # Crop do topo
            crop_filter = f"crop={target_width}:{target_height}:0:0"
        elif crop_position == "bottom":
            # Crop do fundo (calcula posição Y)
            crop_filter = f"crop={target_width}:{target_height}:0:(ih-{target_height})"
        else:
            # Default: center
            crop_filter = f"crop={target_width}:{target_height}"
        
        # Combinar filtros: scale → crop → setsar (garantir aspect ratio)
        video_filter = f"{scale_filter},{crop_filter},setsar=1"
        
        # Calcular duração esperada antes da concatenação
        expected_duration = 0.0
        resolved_video_files: List[str] = []
        logger.info(f"📊 Input videos for concatenation:")

        for i, video_file in enumerate(video_files):
            abs_path = str(Path(video_file).resolve())
            resolved_video_files.append(abs_path)

            # Log duração de cada input (para debug)
            try:
                input_info = await self.get_video_info(str(video_file))
                input_duration = input_info['duration']
                expected_duration += input_duration
                logger.info(f"  [{i+1}] {Path(video_file).name}: {input_duration:.2f}s")
            except Exception as e:
                logger.warning(f"  [{i+1}] {Path(video_file).name}: Could not get duration - {e}")

        logger.info(f"📊 Expected output duration: {expected_duration:.2f}s (sum of {len(video_files)} videos)")

        # FFmpeg com filter_complex concat para evitar truncamento de duração
        # ao aplicar filtros de scale/crop em múltiplos inputs
        cmd = [self.ffmpeg_path, "-y"]
        for video_file in resolved_video_files:
            cmd.extend(["-i", video_file])

        filter_parts = []
        concat_video_inputs = []
        concat_audio_inputs = []

        for i in range(len(resolved_video_files)):
            filter_parts.append(f"[{i}:v]{video_filter}[v{i}]")
            concat_video_inputs.append(f"[v{i}]")

            if not remove_audio:
                filter_parts.append(
                    f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}]"
                )
                concat_audio_inputs.append(f"[a{i}]")

        from ..shared.exceptions import ErrorCode

        if remove_audio:
            filter_parts.append(
                f"{''.join(concat_video_inputs)}concat=n={len(resolved_video_files)}:v=1:a=0[vout]"
            )
        else:
            filter_parts.append(
                f"{''.join(concat_video_inputs)}{''.join(concat_audio_inputs)}"
                f"concat=n={len(resolved_video_files)}:v=1:a=1[vout][aout]"
            )

        filter_complex = ";".join(filter_parts)

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", self.video_codec,
            "-preset", self.preset,
            "-crf", str(self.crf),
        ])

        if remove_audio:
            cmd.append("-an")
        else:
            cmd.extend(["-map", "[aout]", "-c:a", self.audio_codec, "-b:a", "192k"])

        cmd.append(str(output_path))

        logger.info(f"▶️ Running FFmpeg concatenation...")

        # Executar FFmpeg com timeout
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=1800,  # 30 minutes for concatenation (can be long with many videos)
                check=False,
                capture_output=True
            )

            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg error: {error_msg}")
                raise FFmpegFailedException(
                    operation="video concatenation",
                    stderr=error_msg,
                    returncode=returncode,
                    details={"video_count": len(resolved_video_files)}
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFmpeg concatenation timeout: {e}")
            raise FFmpegTimeoutException(
                operation="video concatenation",
                timeout=1800,
                details={"video_count": len(resolved_video_files)},
                cause=e
            )

        # VALIDAÇÃO PÓS-CONCATENAÇÃO (BUG FIX: detectar duplicação)
        output_info = await self.get_video_info(str(output_path))
        actual_duration = output_info['duration']

        logger.info(f"📊 Concatenation result:")
        logger.info(f"  ├─ Expected: {expected_duration:.2f}s")
        logger.info(f"  ├─ Actual: {actual_duration:.2f}s")
        logger.info(f"  └─ Difference: {abs(actual_duration - expected_duration):.2f}s")

        # Tolerância de 2 segundos (devido a keyframes e arredondamentos)
        tolerance = 2.0
        if abs(actual_duration - expected_duration) > tolerance:
            logger.error(
                f"❌ CONCATENATION BUG DETECTED! "
                f"Actual duration ({actual_duration:.2f}s) differs from expected "
                f"({expected_duration:.2f}s) by {abs(actual_duration - expected_duration):.2f}s"
            )
            raise ConcatenationException(
                video_count=len(video_files),
                expected_duration=expected_duration,
                actual_duration=actual_duration,
                reason=f"Duration mismatch: expected {expected_duration:.2f}s, got {actual_duration:.2f}s",
                details={
                    "difference": actual_duration - expected_duration,
                    "tolerance": tolerance
                }
            )

        logger.info(f"✅ Video concatenated successfully: {output_path}")
        return output_path
    
    async def crop_video_for_validation(self,
                                       video_path: str,
                                       output_path: str,
                                       aspect_ratio: str = "9:16",
                                       crop_position: str = "center") -> str:
        """
        🚨 FORÇA BRUTA: Aplica crop 9:16 no vídeo ANTES da validação OCR
        
        CRÍTICO: Esta função garante que o OCR analisa EXATAMENTE o frame que
        será usado no vídeo final, após o crop.
        
        Args:
            video_path: Vídeo original (qualquer aspect ratio)
            output_path: Vídeo cropado para validação
            aspect_ratio: Proporção desejada (9:16, 16:9, 1:1, 4:5)
            crop_position: Posição do crop (center, top, bottom)
        
        Returns:
            Caminho do vídeo cropado
        
        Raises:
            VideoInvalidResolutionException: Se aspect ratio inválido
            VideoEncodingException: Se falhar o crop
            FFmpegTimeoutException: Se operação exceder timeout
        """
        logger.info(f"✂️ Cropping video for OCR validation")
        logger.info(f"   ├─ Input: {video_path}")
        logger.info(f"   ├─ Output: {output_path}")
        logger.info(f"   ├─ Aspect ratio: {aspect_ratio}")
        logger.info(f"   └─ Crop position: {crop_position}")
        
        # Mapear aspect ratios para resoluções
        aspect_map = {
            "9:16": (1080, 1920),   # Vertical (Shorts, Stories)
            "16:9": (1920, 1080),   # Horizontal (YouTube padrão)
            "1:1": (1080, 1080),    # Quadrado (Instagram)
            "4:5": (1080, 1350),    # Instagram Feed
        }
        
        if aspect_ratio not in aspect_map:
            raise VideoInvalidResolutionException(
                aspect_ratio=aspect_ratio,
                valid_ratios=list(aspect_map.keys())
            )
        
        target_width, target_height = aspect_map[aspect_ratio]
        
        # 🚨 USAR OS MESMOS FILTROS DA CONCATENAÇÃO
        # Isso garante que o OCR analisa EXATAMENTE o mesmo frame final
        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase"
        
        if crop_position == "center":
            crop_filter = f"crop={target_width}:{target_height}"
        elif crop_position == "top":
            crop_filter = f"crop={target_width}:{target_height}:0:0"
        elif crop_position == "bottom":
            crop_filter = f"crop={target_width}:{target_height}:0:(ih-{target_height})"
        else:
            crop_filter = f"crop={target_width}:{target_height}"
        
        # Combinar filtros: scale → crop → setsar
        video_filter = f"{scale_filter},{crop_filter},setsar=1"
        
        # Criar diretório de saída se não existir
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg: aplicar crop e remover áudio (validação não precisa de áudio)
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", str(video_path),
            "-vf", video_filter,
            "-an",  # Remover áudio (economia de espaço)
            "-c:v", self.video_codec,
            "-preset", "ultrafast",  # Rápido (é temporário)
            "-crf", "28",  # Qualidade OK para validação
            str(output_path)
        ]
        
        logger.info(f"▶️ Running FFmpeg crop...")
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=300,  # 5 minutes for crop
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg crop error: {error_msg}")
                raise VideoEncodingException(
                    operation="video crop for validation",
                    reason=error_msg,
                    details={"video_path": str(input_path), "crop_filter": crop_filter}
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFmpeg crop timeout: {e}")
            raise FFmpegTimeoutException(
                operation="video crop for validation",
                timeout=300,
                details={"video_path": str(input_path)},
                cause=e
            )
        
        logger.info(f"✅ Video cropped for validation: {output_path}")
        return output_path
    
    async def add_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Adiciona áudio a um vídeo
        
        Args:
            video_path: Caminho do vídeo (sem áudio ou com áudio a ser substituído)
            audio_path: Caminho do arquivo de áudio
            output_path: Caminho do vídeo de saída
        
        Returns:
            Caminho do vídeo gerado
        
        Raises:
            VideoEncodingException: Se falhar a adição de áudio
            FFmpegTimeoutException: Se operação exceder 10min
        """
        
        logger.info(f"🔊 Adding audio to video")
        
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",  # Não re-encode vídeo
            "-c:a", self.audio_codec,
            "-b:a", "192k",
            # REMOVIDO -shortest: O vídeo já foi montado com duração correta
            # e será trimmed no Step 8 para audio_duration + padding
            str(output_path)
        ]
        
        logger.info(f"▶️ Running FFmpeg audio addition...")
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=600,  # 10 minutes for audio addition
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg error: {error_msg}")
                raise VideoEncodingException(
                    operation="audio addition to video",
                    reason=error_msg,
                    details={"video_path": str(video_path), "audio_path": str(audio_path), "return_code": returncode}
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFmpeg audio addition timeout: {e}")
            raise FFmpegTimeoutException(
                operation="audio addition to video",
                timeout=600,
                details={"video_path": str(video_path), "audio_path": str(audio_path)},
                cause=e
            )
        
        logger.info(f"✅ Audio added: {output_path}")
        return output_path
    
    async def burn_subtitles(self, video_path: str, subtitle_path: str, 
                           output_path: str, style: str = "dynamic") -> str:
        """Adiciona legendas hard-coded ao vídeo
        
        Args:
            video_path: Caminho do vídeo
            subtitle_path: Caminho do arquivo SRT
            output_path: Caminho do vídeo de saída
            style: Estilo das legendas (static, dynamic, minimal)
        
        Returns:
            Caminho do vídeo gerado
        
        Raises:
            SubtitleGenerationException: Se arquivo de legenda não existir
            VideoEncodingException: Se falhar burn-in de legendas
            FFmpegTimeoutException: Se operação exceder 15min
        """
        
        logger.info(f"📝 Burning subtitles (style: {style})")

        video_path_obj = Path(video_path).resolve()
        subtitle_path_obj = Path(subtitle_path).resolve()
        output_path_obj = Path(output_path).resolve()
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        if not subtitle_path_obj.exists():
            raise SubtitleGenerationException(
                reason=f"Subtitle file not found: {subtitle_path_obj}",
                subtitle_path=str(subtitle_path_obj),
                details={"expected_path": str(subtitle_path_obj)}
            )

        subtitle_size = subtitle_path_obj.stat().st_size
        if subtitle_size == 0:
            logger.warning(
                f"⚠️ Subtitle file is empty ({subtitle_path_obj}), skipping burn-in and keeping video without subtitles"
            )
            shutil.copy2(video_path_obj, output_path_obj)
            return str(output_path_obj)
        
        # Verificar duração do vídeo de entrada
        input_info = await self.get_video_info(str(video_path_obj))
        input_duration = input_info['duration']
        logger.info(f"📊 Input video duration: {input_duration:.2f}s")
        
        # Estilos de legenda - CENTRO DA TELA, TAMANHO PEQUENO PARA EVITAR SAIR DA TELA
        # Alignment=10 = Topo centro, MarginV=280 empurra para centro
        # FontSize pequeno para palavras grandes não saírem da tela
        styles = {
            "static": "FontSize=20,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280",
            "dynamic": "FontSize=22,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280",
            "minimal": "FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Alignment=10,MarginV=280"
        }
        
        subtitle_style = styles.get(style, styles["dynamic"])
        
        # Escapar caminho do subtitle para FFmpeg
        subtitle_path_escaped = str(subtitle_path_obj).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path_obj),
            "-vf", f"subtitles={subtitle_path_escaped}:force_style='{subtitle_style}'",
            "-c:a", "copy",  # Não re-encode áudio
            "-map", "0:v:0",  # BUG FIX: Mapear APENAS primeiro stream de vídeo
            "-map", "0:a:0",  # BUG FIX: Mapear APENAS primeiro stream de áudio
            "-y",
            str(output_path_obj)
        ]
        
        logger.info(f"▶️ Running FFmpeg subtitle burn-in...")
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=900,  # 15 minutes for subtitle burn-in (can be slow with many subs)
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg error: {error_msg}")
                raise VideoEncodingException(
                    operation="subtitle burn-in",
                    reason=error_msg,
                    details={"video_path": str(video_path), "subtitle_path": str(subtitle_path), "return_code": returncode}
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFmpeg subtitle burn-in timeout: {e}")
            raise FFmpegTimeoutException(
                operation="subtitle burn-in",
                timeout=900,
                details={"video_path": str(video_path), "subtitle_path": str(subtitle_path)},
                cause=e
            )
        
        # VALIDAÇÃO PÓS-BURN (verificar se duração se manteve)
        output_info = await self.get_video_info(str(output_path_obj))
        output_duration = output_info['duration']
        
        logger.info(f"📊 Subtitle burn result:")
        logger.info(f"  ├─ Input: {input_duration:.2f}s")
        logger.info(f"  └─ Output: {output_duration:.2f}s")
        
        # Tolerância de 1 segundo
        if abs(output_duration - input_duration) > 1.0:
            logger.warning(
                f"⚠️ Duration changed after subtitle burn: "
                f"{input_duration:.2f}s → {output_duration:.2f}s "
                f"(diff: {abs(output_duration - input_duration):.2f}s)"
            )
        
        logger.info(f"✅ Subtitles burned: {output_path_obj}")
        return str(output_path_obj)
    
    async def trim_video(self, video_path: str, output_path: str, 
                        max_duration: float) -> str:
        """Trim vídeo para duração máxima especificada
        
        Args:
            video_path: Caminho do vídeo a ser trimmed
            output_path: Caminho do vídeo de saída
            max_duration: Duração máxima em segundos (ex: audio_duration + padding)
        
        Returns:
            Caminho do vídeo gerado
        
        Raises:
            VideoEncodingException: Se falhar o trim
            FFmpegTimeoutException: Se operação exceder 10min
        
        Note:
            - Usa re-encode (libx264) para precisão frame-accurate
            - Stream copy (-c copy) não funciona bem para trim preciso (apenas keyframes)
            - Trade-off: mais lento (~2-5s) mas preciso ao milissegundo
        """
        
        logger.info(f"✂️ Trimming video to {max_duration:.2f}s (re-encode mode for precision)")
        
        # RE-ENCODE para precisão (BUG FIX: stream copy causava imprecisão +20s)
        # Usar -t para limitar duração de saída
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-t", str(max_duration),  # Duração máxima de saída
            "-c:v", "libx264",        # Re-encode vídeo (preciso)
            "-c:a", "aac",            # Re-encode áudio
            "-preset", "fast",        # Balanço velocidade/qualidade
            "-crf", "23",             # Qualidade boa (18=melhor, 28=menor)
            "-map", "0:v:0",          # Mapear APENAS primeiro stream de vídeo
            "-map", "0:a:0",          # Mapear APENAS primeiro stream de áudio
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path)
        ]
        
        logger.info(f"▶️ Running FFmpeg trim (re-encode for precision)...")
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=600,  # 10 minutes for trim
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg trim error: {error_msg}")
                raise VideoEncodingException(
                    operation="video trim",
                    reason=error_msg,
                    details={"video_path": str(video_path), "max_duration": max_duration, "return_code": returncode}
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFmpeg trim timeout: {e}")
            raise FFmpegTimeoutException(
                operation="video trim",
                timeout=600,
                details={"video_path": str(video_path), "max_duration": max_duration},
                cause=e
            )
        
        logger.info(f"✅ Video trimmed to {max_duration:.2f}s: {output_path}")
        return output_path
    
    async def get_video_info(self, video_path: str) -> Dict:
        """Extrai informações do vídeo usando ffprobe
        
        Args:
            video_path: Caminho do vídeo
        
        Returns:
            Dicionário com informações do vídeo
        
        Raises:
            FFprobeFailedException: Se ffprobe falhar ou timeout
            VideoCorruptedException: Se vídeo estiver corrupto ou sem streams
        """
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=30,  # 30 seconds for ffprobe
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFprobe error: {error_msg}")
                raise FFprobeFailedException(
                    video_path=str(video_path),
                    stderr=error_msg,
                    returncode=returncode
                )
        
        except SubprocessTimeoutException as e:
            logger.error(f"❌ FFprobe timeout: {e}")
            raise FFprobeFailedException(
                video_path=str(video_path),
                stderr="FFprobe timeout after 30s",
                returncode=-1,
                cause=e
            )
        
        try:
            info = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason="Failed to parse ffprobe JSON output",
                details={"json_error": str(e)}
            )
        
        # Extrair informações relevantes
        video_stream = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
        
        if not video_stream:
            raise VideoCorruptedException(
                video_path=str(video_path),
                reason="No video stream found in file"
            )
        
        result = {
            "duration": float(info["format"]["duration"]),
            "size": int(info["format"]["size"]),
            "resolution": f"{video_stream['width']}x{video_stream['height']}",
            "width": video_stream['width'],
            "height": video_stream['height'],
            "codec": video_stream["codec_name"],
        }
        
        # FPS pode estar em diferentes formatos
        if "r_frame_rate" in video_stream:
            try:
                fps_parts = video_stream["r_frame_rate"].split('/')
                if len(fps_parts) == 2:
                    result["fps"] = int(fps_parts[0]) / int(fps_parts[1])
                else:
                    result["fps"] = float(fps_parts[0]) if fps_parts else 30
            except (ValueError, ZeroDivisionError):
                result["fps"] = 30  # Default
        else:
            result["fps"] = 30
        
        return result
    
    async def get_audio_duration(self, audio_path: str) -> float:
        """Obtém duração de um arquivo de áudio
        
        Args:
            audio_path: Caminho do arquivo de áudio
        
        Returns:
            Duração em segundos
        
        Raises:
            AudioNotFoundException: Se arquivo de áudio não existir
            AudioCorruptedException: Se áudio estiver corrupto ou falhar parse
        """
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_path)
        ]
        
        try:
            from ..infrastructure.subprocess_utils import run_subprocess_with_timeout
            
            returncode, stdout, stderr = await run_subprocess_with_timeout(
                cmd=cmd,
                timeout=30,  # 30 seconds for ffprobe audio
                check=False,
                capture_output=True
            )
            
            if returncode != 0:
                error_msg = stderr.decode()
                from ..shared.exceptions import ErrorCode
                
                # Melhorar mensagem de erro com detalhes do FFprobe
                if "Invalid data found" in error_msg or "moov atom not found" in error_msg:
                    raise AudioCorruptedException(
                        audio_path=str(audio_path),
                        reason="Audio file is corrupted or not a valid audio file",
                        details={"ffprobe_error": error_msg[:500], "hint": "Upload a valid MP3, WAV, M4A, or OGG file"}
                    )
                elif "No such file" in error_msg:
                    raise AudioNotFoundException(
                        audio_path=str(audio_path),
                        expected_location=str(audio_path)
                    )
                else:
                    raise AudioCorruptedException(
                        audio_path=str(audio_path),
                        reason=f"FFprobe failed: {error_msg.split(':')[-1].strip()[:200] if error_msg else 'Unknown error'}",
                        details={"ffprobe_error": error_msg[:500]}
                    )
        
            # Parse JSON output
            info = json.loads(stdout.decode())
            duration = float(info["format"]["duration"])
            logger.info(f"🎵 Audio duration: {duration:.2f}s")
            return duration
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise AudioCorruptedException(
                audio_path=str(audio_path),
                reason="Failed to parse audio duration from ffprobe output",
                details={"parse_error": str(e)}
            )
