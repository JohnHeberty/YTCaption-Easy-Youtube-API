"""
Video Builder

Responsável pela montagem de vídeos usando FFmpeg.
Implementa APENAS processamento de vídeo - NÃO baixa vídeos.
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Tuple

from ..shared.exceptions import VideoProcessingException

logger = logging.getLogger(__name__)


class VideoBuilder:
    """Construtor de vídeos usando FFmpeg"""
    
    def __init__(self, temp_dir: str, output_dir: str, 
                 video_codec: str = "libx264",
                 audio_codec: str = "aac",
                 preset: str = "fast",
                 crf: int = 23):
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.preset = preset
        self.crf = crf
        
        # Criar diretórios se não existirem
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎬 VideoBuilder initialized")
        logger.info(f"   ├─ Temp dir: {self.temp_dir}")
        logger.info(f"   ├─ Output dir: {self.output_dir}")
        logger.info(f"   ├─ Video codec: {self.video_codec}")
        logger.info(f"   ├─ Audio codec: {self.audio_codec}")
        logger.info(f"   ├─ Preset: {self.preset}")
        logger.info(f"   └─ CRF: {self.crf}")
    
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
            VideoProcessingException: Se falhar a concatenação
        """
        
        logger.info(f"🎬 Concatenating {len(video_files)} videos")
        logger.info(f"   ├─ Aspect ratio: {aspect_ratio}")
        logger.info(f"   ├─ Crop position: {crop_position}")
        logger.info(f"   └─ Remove audio: {remove_audio}")
        
        # Mapear aspect ratios para resoluções
        aspect_map = {
            "9:16": (1080, 1920),   # Vertical (Shorts, Stories)
            "16:9": (1920, 1080),   # Horizontal (YouTube padrão)
            "1:1": (1080, 1080),    # Quadrado (Instagram)
            "4:5": (1080, 1350),    # Instagram Feed
        }
        
        if aspect_ratio not in aspect_map:
            raise VideoProcessingException(
                f"Invalid aspect ratio: {aspect_ratio}",
                {"valid_ratios": list(aspect_map.keys())}
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
        
        # Criar lista de concatenação
        concat_list_path = self.temp_dir / f"concat_list_{Path(output_path).stem}.txt"
        
        try:
            # Calcular duração esperada antes da concatenação
            expected_duration = 0.0
            logger.info(f"📊 Input videos for concatenation:")
            
            with open(concat_list_path, "w", encoding='utf-8') as f:
                for i, video_file in enumerate(video_files):
                    # FFmpeg concat demangle requer path absoluto
                    abs_path = Path(video_file).resolve()
                    f.write(f"file '{abs_path}'\n")
                    
                    # Log duração de cada input (para debug)
                    try:
                        input_info = await self.get_video_info(str(video_file))
                        input_duration = input_info['duration']
                        expected_duration += input_duration
                        logger.info(f"  [{i+1}] {Path(video_file).name}: {input_duration:.2f}s")
                    except Exception as e:
                        logger.warning(f"  [{i+1}] {Path(video_file).name}: Could not get duration - {e}")
            
            logger.info(f"📊 Expected output duration: {expected_duration:.2f}s (sum of {len(video_files)} videos)")
            
            # FFmpeg command
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-vf", video_filter,  # Usar o filtro corrigido
                "-c:v", self.video_codec,
                "-preset", self.preset,
                "-crf", str(self.crf),
            ]
            
            if remove_audio:
                cmd.append("-an")  # Remove áudio
            else:
                cmd.extend(["-c:a", self.audio_codec, "-b:a", "192k"])
            
            cmd.append(str(output_path))
            
            logger.info(f"▶️ Running FFmpeg concatenation...")
            
            # Executar FFmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg error: {error_msg}")
                raise VideoProcessingException(
                    "FFmpeg concatenation failed",
                    {"ffmpeg_error": error_msg, "return_code": process.returncode}
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
                raise VideoProcessingException(
                    "Concatenation resulted in incorrect duration",
                    {
                        "expected_duration": expected_duration,
                        "actual_duration": actual_duration,
                        "difference": actual_duration - expected_duration,
                        "tolerance": tolerance,
                        "input_count": len(video_files)
                    }
                )
            
            logger.info(f"✅ Video concatenated successfully: {output_path}")
            return output_path
        
        finally:
            # Limpar arquivo temporário
            if concat_list_path.exists():
                concat_list_path.unlink()
    
    async def add_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Adiciona áudio a um vídeo
        
        Args:
            video_path: Caminho do vídeo (sem áudio ou com áudio a ser substituído)
            audio_path: Caminho do arquivo de áudio
            output_path: Caminho do vídeo de saída
        
        Returns:
            Caminho do vídeo gerado
        
        Raises:
            VideoProcessingException: Se falhar a adição de áudio
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
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"❌ FFmpeg error: {error_msg}")
            raise VideoProcessingException(
                "FFmpeg audio addition failed",
                {"ffmpeg_error": error_msg, "return_code": process.returncode}
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
            VideoProcessingException: Se falhar burn-in de legendas
        """
        
        logger.info(f"📝 Burning subtitles (style: {style})")
        
        # Verificar duração do vídeo de entrada
        input_info = await self.get_video_info(str(video_path))
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
        subtitle_path_escaped = str(subtitle_path).replace("\\", "\\\\").replace(":", "\\:")
        
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-vf", f"subtitles={subtitle_path_escaped}:force_style='{subtitle_style}'",
            "-c:a", "copy",  # Não re-encode áudio
            "-map", "0:v:0",  # BUG FIX: Mapear APENAS primeiro stream de vídeo
            "-map", "0:a:0",  # BUG FIX: Mapear APENAS primeiro stream de áudio
            "-y",
            str(output_path)
        ]
        
        logger.info(f"▶️ Running FFmpeg subtitle burn-in...")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"❌ FFmpeg error: {error_msg}")
            raise VideoProcessingException(
                "FFmpeg subtitle burn-in failed",
                {"ffmpeg_error": error_msg, "return_code": process.returncode}
            )
        
        # VALIDAÇÃO PÓS-BURN (verificar se duração se manteve)
        output_info = await self.get_video_info(str(output_path))
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
        
        logger.info(f"✅ Subtitles burned: {output_path}")
        return output_path
    
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
            VideoProcessingException: Se falhar o trim
        
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
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"❌ FFmpeg trim error: {error_msg}")
            raise VideoProcessingException(
                "FFmpeg video trim failed",
                {"ffmpeg_error": error_msg, "return_code": process.returncode}
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
            VideoProcessingException: Se falhar a extração de informações
        """
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error(f"❌ FFprobe error: {error_msg}")
            raise VideoProcessingException(
                "FFprobe failed",
                {"ffprobe_error": error_msg, "return_code": process.returncode}
            )
        
        try:
            info = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            raise VideoProcessingException(
                "Failed to parse ffprobe output",
                {"error": str(e)}
            )
        
        # Extrair informações relevantes
        video_stream = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), None)
        
        if not video_stream:
            raise VideoProcessingException("No video stream found")
        
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
            VideoProcessingException: Se falhar a extração de duração
        """
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            raise VideoProcessingException(
                "Failed to get audio duration",
                {"ffprobe_error": error_msg}
            )
        
        try:
            info = json.loads(stdout.decode())
            duration = float(info["format"]["duration"])
            logger.info(f"🎵 Audio duration: {duration:.2f}s")
            return duration
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise VideoProcessingException(
                "Failed to parse audio duration",
                {"error": str(e)}
            )
