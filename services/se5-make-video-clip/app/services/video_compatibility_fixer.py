"""
Video Compatibility Fixer

Módulo responsável por garantir compatibilidade entre vídeos para concatenação.
Corrige automaticamente:
- Resoluções diferentes
- Codecs incompatíveis  
- Frame rates diferentes
- Aspect ratios diferentes
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.shared.exceptions_v2 import (
    FFmpegFailedException,
    VideoNotFoundException,
    FFmpegTimeoutException
)
from app.core.config import get_settings
from common.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class VideoSpec:
    """Especificações de vídeo para normalização"""
    width: int
    height: int
    fps: float
    codec: str
    audio_codec: str
    audio_sample_rate: int
    
    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"
    
    @property
    def aspect_ratio(self) -> str:
        from math import gcd
        divisor = gcd(self.width, self.height)
        return f"{self.width // divisor}:{self.height // divisor}"

class VideoCompatibilityFixer:
    """
    Garante compatibilidade entre vídeos para concatenação.
    
    Estratégias:
    1. Detectar especificações de todos os vídeos
    2. Escolher especificações-alvo (mais comum ou primeira)
    3. Converter vídeos incompatíveis para especificações-alvo
    4. Validar resultado
    """
    
    # Especificações padrão (fallback) - 720p HD
    DEFAULT_SPECS = VideoSpec(
        width=1280,
        height=720,
        fps=30.0,
        codec="libx264",
        audio_codec="aac",
        audio_sample_rate=48000
    )
    
    def __init__(self):
        self.settings = get_settings()
        self.target_resolution = VideoSpec(
            width=self.settings["target_video_width"],
            height=self.settings["target_video_height"],
            fps=self.settings["target_video_fps"],
            codec=self.settings["target_video_codec"],
            audio_codec="aac",
            audio_sample_rate=48000
        )
        
    async def ensure_compatibility(
        self,
        video_paths: List[Path],
        output_dir: Path,
        target_spec: Optional[VideoSpec] = None,
        force_reconvert: bool = False
    ) -> List[Path]:
        """
        Garante que todos os vídeos sejam compatíveis.
        
        Args:
            video_paths: Lista de caminhos dos vídeos originais
            output_dir: Diretório para salvar vídeos convertidos
            target_spec: Especificações-alvo (None = detectar automaticamente)
            force_reconvert: Forçar reconversão mesmo se já compatível
            
        Returns:
            Lista de caminhos dos vídeos compatíveis (originais ou convertidos)
            
        Raises:
            VideoNotFoundException: Se algum vídeo não existir
            FFmpegFailedException: Se conversão falhar
        """
        logger.info(f"🔧 Iniciando compatibilização de {len(video_paths)} vídeos")
        
        # Validar que todos existem
        for video_path in video_paths:
            if not video_path.exists():
                raise VideoNotFoundException(video_path=str(video_path))
        
        # Se só tem 1 vídeo, não precisa compatibilizar
        if len(video_paths) == 1:
            logger.info("✅ Apenas 1 vídeo, não precisa compatibilização")
            return video_paths
        
        # Detectar especificações de todos os vídeos
        specs_map = await self._detect_all_specs(video_paths)
        
        # Determinar especificação-alvo
        if target_spec is None:
            target_spec = self._determine_target_spec(specs_map, video_paths)
        
        logger.info(f"🎯 Especificação-alvo: {target_spec.resolution} @ {target_spec.fps}fps")
        
        # Diretório temporário para conversões (mesmo diretório dos vídeos)
        temp_dir = video_paths[0].parent / ".temp_conversion"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Processar cada vídeo
        tasks = []
        videos_to_keep = []
        
        for video_path in video_paths:
            current_spec = specs_map[video_path]
            
            # Verificar se precisa conversão
            needs_conversion = (
                force_reconvert or
                not self._is_compatible(current_spec, target_spec)
            )
            
            if needs_conversion:
                logger.info(f"🔄 {video_path.name}: {current_spec.resolution} → {target_spec.resolution}")
                # Converter para arquivo temporário
                temp_path = temp_dir / f"temp_{video_path.name}"
                task = self._convert_and_replace(video_path, temp_path, target_spec)
                tasks.append(task)
            else:
                logger.info(f"✅ {video_path.name}: Já compatível")
                videos_to_keep.append(video_path)
        
        # Executar conversões em paralelo (máximo 3 simultâneas)
        if tasks:
            semaphore = asyncio.Semaphore(3)
            
            async def convert_with_limit(task):
                async with semaphore:
                    return await task
            
            await asyncio.gather(
                *[convert_with_limit(t) for t in tasks]
            )
        
        # Limpar diretório temporário
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        
        logger.info(f"✅ Compatibilização completa: {len(video_paths)} vídeos prontos (originais sobrescritos)")
        return video_paths  # Retornar mesmos paths (agora convertidos no lugar)
    
    async def _detect_all_specs(
        self,
        video_paths: List[Path]
    ) -> Dict[Path, VideoSpec]:
        """Detecta especificações de todos os vídeos em paralelo."""
        tasks = [self._detect_specs(vp) for vp in video_paths]
        specs_list = await asyncio.gather(*tasks)
        return dict(zip(video_paths, specs_list))
    
    async def _detect_specs(self, video_path: Path) -> VideoSpec:
        """Detecta especificações de um vídeo."""
        try:
            # Executar ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            if process.returncode != 0:
                raise Exception(f"FFprobe failed: {stderr.decode()}")
            
            metadata = json.loads(stdout.decode())
            
            # Encontrar stream de vídeo
            video_stream = None
            for stream in metadata.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise Exception("No video stream found")
            
            return VideoSpec(
                width=video_stream.get('width', 1080),
                height=video_stream.get('height', 1920),
                fps=self._parse_fps(video_stream.get('r_frame_rate', '30/1')),
                codec=video_stream.get('codec_name', 'h264'),
                audio_codec='aac',  # Sempre normalizar para AAC
                audio_sample_rate=48000  # Sempre normalizar para 48kHz
            )
        except Exception as e:
            logger.warning(f"⚠️  Erro ao detectar specs de {video_path.name}: {e}")
            return self.DEFAULT_SPECS
    
    def _parse_fps(self, fps_str: str) -> float:
        """Parse FPS string (ex: '30/1' ou '30.0')."""
        try:
            if '/' in fps_str:
                num, den = fps_str.split('/')
                return float(num) / float(den)
            return float(fps_str)
        except:
            return 30.0
    
    def _determine_target_spec(
        self,
        specs_map: Dict[Path, VideoSpec],
        video_paths: List[Path]
    ) -> VideoSpec:
        """
        Determina especificação-alvo usando configuração do .env.
        Padrão: 1280x720 @ 30fps (HD 720p)
        """
        # Usar resolução configurada no .env
        target = self.target_resolution
        
        logger.info(f"📊 Usando resolução padrão configurada (HD {self.settings['target_video_height']}p)")
        logger.info(f"   Resolution: {target.resolution}")
        logger.info(f"   FPS: {target.fps}")
        logger.info(f"   Codec: {target.codec}")
        
        return target
    
    def _is_compatible(self, current: VideoSpec, target: VideoSpec) -> bool:
        """Verifica se vídeo é compatível com especificação-alvo."""
        # Tolerar pequenas diferenças em FPS (±0.5)
        fps_compatible = abs(current.fps - target.fps) < 0.5
        
        return (
            current.width == target.width and
            current.height == target.height and
            fps_compatible
        )
    
    async def _convert_and_replace(
        self,
        original_path: Path,
        temp_path: Path,
        target_spec: VideoSpec
    ) -> None:
        """
        Converte vídeo para especificações-alvo e substitui o original.
        
        Raises:
            FFmpegFailedException: Se conversão falhar
        """
        try:
            # Construir comando FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', str(original_path),
                
                # Video filters
                '-vf', f"scale={target_spec.width}:{target_spec.height}:force_original_aspect_ratio=decrease,pad={target_spec.width}:{target_spec.height}:(ow-iw)/2:(oh-ih)/2,fps={target_spec.fps}",
                
                # Video codec
                '-c:v', target_spec.codec,
                '-preset', 'medium',
                '-crf', '23',
                
                # Audio
                '-c:a', target_spec.audio_codec,
                '-ar', str(target_spec.audio_sample_rate),
                '-ac', '2',  # Stereo
                '-b:a', '128k',
                
                # Output para temp
                str(temp_path)
            ]
            
            logger.debug(f"🎬 FFmpeg command: {' '.join(cmd)}")
            
            # Executar conversão com timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300  # 5 minutos por vídeo
                )
            except asyncio.TimeoutError:
                process.kill()
                raise FFmpegTimeoutException(
                    command=' '.join(cmd),
                    timeout=300
                )
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise FFmpegFailedException(
                    file_path=str(original_path),
                    reason=f"FFmpeg failed: {error_msg[:200]}"
                )
            
            # Validar que arquivo foi criado
            if not temp_path.exists():
                raise FFmpegFailedException(
                    file_path=str(original_path),
                    reason="Output file not created"
                )
            
            # Substituir original pelo convertido
            import shutil
            shutil.move(str(temp_path), str(original_path))
            
            logger.info(f"✅ Conversão completa e original substituído: {original_path.name}")
            
        except Exception as e:
            # Limpar arquivo temporário se houver erro
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    async def reprocess_incompatible_videos(
        self,
        video_dir: Path,
        pattern: str = "*.mp4"
    ) -> Dict[str, any]:
        """
        Re-processa vídeos incompatíveis em um diretório.
        Útil para corrigir vídeos já baixados.
        
        NOTA: Os vídeos são convertidos IN-PLACE (sobrescrevem os originais).
        
        Returns:
            Estatísticas do processamento
        """
        logger.info(f"🔧 Re-processando vídeos em {video_dir}")
        
        video_files = sorted(video_dir.glob(pattern))
        
        if not video_files:
            logger.warning(f"⚠️  Nenhum vídeo encontrado em {video_dir}")
            return {"processed": 0, "converted": 0, "errors": 0}
        
        # Detectar quais precisam conversão ANTES de convertê-los
        target_spec = self._determine_target_spec({}, [])  # Usa defaults do .env
        needs_conversion = []
        
        for video_file in video_files:
            spec = await self._detect_specs(video_file)
            if not self._is_compatible(spec, target_spec):
                needs_conversion.append(video_file)
        
        try:
            # ensure_compatibility agora sobrescreve no lugar
            await self.ensure_compatibility(
                video_files,
                output_dir=None,  # Não usado mais
                target_spec=None,
                force_reconvert=False
            )
            
            converted_count = len(needs_conversion)
            
            return {
                "processed": len(video_files),
                "converted": converted_count,
                "already_compatible": len(video_files) - converted_count,
                "errors": 0
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no reprocessamento: {e}")
            return {
                "processed": len(video_files),
                "converted": 0,
                "errors": 1,
                "error_message": str(e)
            }
