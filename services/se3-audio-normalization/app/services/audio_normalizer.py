"""
Audio Normalizer - Responsável pelas operações de normalização de áudio
Princípio: Single Responsibility + Open/Closed
"""
import asyncio
import numpy as np
import subprocess
import tempfile
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
import noisereduce as nr
import soundfile as sf
import librosa

from ..shared.exceptions import AudioNormalizationException
from common.log_utils import get_logger

logger = get_logger(__name__)

class AudioNormalizer:
    """Aplica operações de normalização em arquivos de áudio"""
    
    def __init__(self, config: dict):
        self.config = config
        self.temp_dir = Path(config.get('temp_dir', './data/temp'))
        self.noise_reduction_config = config.get('noise_reduction', {})
        self.highpass_config = config.get('highpass_filter', {})
        self.ffmpeg_config = config.get('ffmpeg', {})
    
    async def normalize_audio(
        self,
        input_path: str,
        output_path: str,
        remove_noise: bool = False,
        convert_to_mono: bool = False,
        apply_highpass: bool = False,
        set_sample_rate_16k: bool = False,
        isolate_vocals: bool = False,
        progress_callback=None
    ) -> str:
        """
        Aplica normalização completa em arquivo de áudio
        
        Args:
            input_path: Caminho do arquivo de entrada
            output_path: Caminho do arquivo de saída
            remove_noise: Aplicar redução de ruído
            convert_to_mono: Converter para mono
            apply_highpass: Aplicar filtro high-pass
            set_sample_rate_16k: Definir sample rate para 16kHz
            isolate_vocals: Isolar vocais
            progress_callback: Função de callback para progresso
            
        Returns:
            Caminho do arquivo normalizado
        """
        try:
            logger.info(f"🔊 Starting audio normalization")
            logger.info(f"   Input: {Path(input_path).name}")
            logger.info(f"   Operations: noise={remove_noise}, mono={convert_to_mono}, "
                       f"highpass={apply_highpass}, 16k={set_sample_rate_16k}, vocals={isolate_vocals}")
            
            current_file = input_path
            step = 0
            total_steps = sum([
                remove_noise,
                isolate_vocals,
                apply_highpass,
                convert_to_mono or set_sample_rate_16k,  # Combined in one step
                True  # Final conversion
            ])
            
            # Step 1: Remove noise if requested
            if remove_noise:
                step += 1
                if progress_callback:
                    await progress_callback(step / total_steps * 100, "Removing noise")
                current_file = await self._remove_noise(current_file)
            
            # Step 2: Isolate vocals if requested
            if isolate_vocals:
                step += 1
                if progress_callback:
                    await progress_callback(step / total_steps * 100, "Isolating vocals")
                current_file = await self._isolate_vocals(current_file)
            
            # Step 3: Apply highpass filter if requested
            if apply_highpass:
                step += 1
                if progress_callback:
                    await progress_callback(step / total_steps * 100, "Applying highpass filter")
                current_file = await self._apply_highpass_filter(current_file)
            
            # Step 4: Convert to mono and/or 16kHz if requested
            if convert_to_mono or set_sample_rate_16k:
                step += 1
                if progress_callback:
                    await progress_callback(step / total_steps * 100, "Converting audio format")
                current_file = await self._convert_audio_format(
                    current_file,
                    to_mono=convert_to_mono,
                    sample_rate=16000 if set_sample_rate_16k else None
                )
            
            # Step 5: Final conversion to output format
            step += 1
            if progress_callback:
                await progress_callback(step / total_steps * 100, "Final conversion")
            
            final_path = await self._convert_to_output_format(current_file, output_path)
            
            if progress_callback:
                await progress_callback(100, "Completed")
            
            logger.info(f"✅ Normalization completed: {Path(final_path).name}")
            return final_path
            
        except Exception as e:
            logger.error(f"❌ Normalization failed: {e}")
            raise AudioNormalizationException(f"Normalization failed: {str(e)}")
    
    async def _remove_noise(self, input_path: str) -> str:
        """Remove ruído de fundo do áudio"""
        try:
            logger.info("🔇 Removing background noise...")
            
            # Load audio
            y, sr = librosa.load(input_path, sr=self.noise_reduction_config.get('sample_rate', 22050))
            
            # Apply noise reduction
            y_denoised = nr.reduce_noise(y=y, sr=sr, prop_decrease=0.8)
            
            # Save to temp file
            output_path = self.temp_dir / f"denoised_{Path(input_path).stem}.wav"
            sf.write(str(output_path), y_denoised, sr)
            
            logger.info(f"✅ Noise removed: {output_path.name}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Noise removal failed: {e}")
            raise AudioNormalizationException(f"Noise removal failed: {str(e)}")
    
    async def _isolate_vocals(self, input_path: str) -> str:
        """Isola vocais usando separação de fontes"""
        try:
            logger.info("🎤 Isolating vocals...")
            
            # Load audio
            y, sr = librosa.load(input_path, sr=self.noise_reduction_config.get('sample_rate', 44100))
            
            # Simple vocal isolation using harmonic-percussive separation
            # For better results, you could use Spleeter or Demucs
            y_harmonic, y_percussive = librosa.effects.hpss(y)
            
            # Save harmonic component (vocals are mostly harmonic)
            output_path = self.temp_dir / f"vocals_{Path(input_path).stem}.wav"
            sf.write(str(output_path), y_harmonic, sr)
            
            logger.info(f"✅ Vocals isolated: {output_path.name}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Vocal isolation failed: {e}")
            raise AudioNormalizationException(f"Vocal isolation failed: {str(e)}")
    
    async def _apply_highpass_filter(self, input_path: str) -> str:
        """Aplica filtro high-pass para remover frequências baixas"""
        try:
            logger.info("📶 Applying highpass filter...")
            
            # Load with pydub
            audio = AudioSegment.from_file(input_path)
            
            # Apply highpass filter
            cutoff = self.highpass_config.get('cutoff_hz', 80)
            filtered = high_pass_filter(audio, cutoff)
            
            # Save to temp file
            output_path = self.temp_dir / f"highpass_{Path(input_path).stem}.wav"
            filtered.export(str(output_path), format="wav")
            
            logger.info(f"✅ Highpass filter applied: {output_path.name}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Highpass filter failed: {e}")
            raise AudioNormalizationException(f"Highpass filter failed: {str(e)}")
    
    async def _convert_audio_format(
        self,
        input_path: str,
        to_mono: bool = False,
        sample_rate: int = None
    ) -> str:
        """Converte formato do áudio (mono/stereo, sample rate)"""
        try:
            logger.info(f"🔄 Converting audio format (mono={to_mono}, sr={sample_rate})")
            
            # Load audio
            audio = AudioSegment.from_file(input_path)
            
            # Convert to mono if requested
            if to_mono and audio.channels > 1:
                audio = audio.set_channels(1)
                logger.info("   └─ Converted to mono")
            
            # Change sample rate if requested
            if sample_rate and audio.frame_rate != sample_rate:
                audio = audio.set_frame_rate(sample_rate)
                logger.info(f"   └─ Sample rate changed to {sample_rate}Hz")
            
            # Normalize volume
            audio = normalize(audio)
            
            # Save to temp file
            output_path = self.temp_dir / f"converted_{Path(input_path).stem}.wav"
            audio.export(str(output_path), format="wav")
            
            logger.info(f"✅ Format conversion completed: {output_path.name}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Format conversion failed: {e}")
            raise AudioNormalizationException(f"Format conversion failed: {str(e)}")
    
    async def _convert_to_output_format(self, input_path: str, output_path: str) -> str:
        """Converte para formato de saída final (webm/opus)"""
        try:
            logger.info(f"📦 Converting to output format: {Path(output_path).suffix}")
            
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # FFmpeg command for final conversion
            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:a", self.ffmpeg_config.get('audio_codec', 'libopus'),
                "-b:a", self.ffmpeg_config.get('audio_bitrate', '128k'),
                "-vn",  # No video
                "-y",  # Overwrite
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"❌ FFmpeg conversion failed: {error_msg[:500]}")
                raise AudioNormalizationException(f"Output conversion failed: {error_msg[:200]}")
            
            if not Path(output_path).exists():
                raise AudioNormalizationException("Output file not created")
            
            output_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            logger.info(f"✅ Output file created: {Path(output_path).name} ({output_size_mb:.2f}MB)")
            
            return output_path
            
        except asyncio.TimeoutError:
            raise AudioNormalizationException("Output conversion timeout")
        except Exception as e:
            logger.error(f"❌ Output conversion failed: {e}")
            raise AudioNormalizationException(f"Output conversion failed: {str(e)}")
