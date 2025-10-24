import os
import logging
import numpy as np
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize, compress_dynamic_range
import noisereduce as nr
import soundfile as sf
from scipy import signal

from .models import Job, JobStatus

logger = logging.getLogger(__name__)

# Importa Spleeter apenas quando necessário (lazy load)
_spleeter_separator = None

def get_spleeter_separator():
    """Lazy load do Spleeter (só carrega quando necessário)"""
    global _spleeter_separator
    if _spleeter_separator is None:
        from spleeter.separator import Separator
        _spleeter_separator = Separator('spleeter:2stems')  # 2 stems: vocals + accompaniment
        logger.info("✅ Spleeter carregado (modelo 2stems)")
    return _spleeter_separator


class AudioProcessor:
    """Processador de áudio para normalização"""
    
    def __init__(self, output_dir: str = "./processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Cria diretório temp para arquivos temporários
        self.temp_dir = Path("./temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Referência para o job store será injetada
        self.job_store = None
    
    def _update_progress(self, job: Job, progress: float, message: str = ""):
        """Atualiza progresso do job"""
        job.progress = min(progress, 99.9)
        if self.job_store:
            self.job_store.update_job(job)
        logger.info(f"Job {job.id}: {progress:.1f}% - {message}")
    
    def process_audio(self, job: Job) -> Job:
        """
        Processa áudio com as operações solicitadas:
        1. Remove ruído (noise reduction)
        2. Normaliza volume
        3. Converte para mono
        """
        try:
            job.status = JobStatus.PROCESSING
            self._update_progress(job, 5.0, "Iniciando processamento")
            
            input_path = Path(job.input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {job.input_file}")
            
            # Armazena tamanho do arquivo original
            job.file_size_input = input_path.stat().st_size
            
            # Gera nome do arquivo de saída usando job.id (hash + operações)
            # Ex: abc123def_nvm_normalized.mp3
            output_filename = f"{job.id}_normalized{input_path.suffix}"
            output_path = self.output_dir / output_filename
            
            # Carrega áudio
            self._update_progress(job, 5.0, "Carregando áudio")
            audio = AudioSegment.from_file(str(input_path))
            
            # Passo 0: Isola voz (se solicitado) - ANTES de tudo
            if job.isolate_vocals:
                self._update_progress(job, 10.0, "Isolando voz com IA (pode demorar 30-90s)")
                audio = self._isolate_vocals(input_path, job)
                self._update_progress(job, 25.0, "Voz isolada com sucesso")
            else:
                self._update_progress(job, 10.0, "Pulando isolamento de voz")
            
            # Passo 1: Converte para mono PRIMEIRO (otimização para voz)
            self._update_progress(job, 30.0, "Convertendo para mono (voz)")
            if audio.channels > 1:
                audio = audio.set_channels(1)
            
            # Passo 2: Reduz sample rate para 16kHz (ideal para voz)
            self._update_progress(job, 35.0, "Otimizando para voz (16kHz)")
            if audio.frame_rate > 16000:
                audio = audio.set_frame_rate(16000)
            
            # Passo 3: High-Pass Filter (remove frequências < 80Hz)
            self._update_progress(job, 40.0, "Removendo frequências graves inaudíveis")
            audio = self._apply_highpass_filter(audio, cutoff=80)
            
            # Passo 4: Remove ruído
            if job.remove_noise:
                self._update_progress(job, 45.0, "Removendo ruído de fundo")
                audio = self._remove_noise(audio, job)
                self._update_progress(job, 70.0, "Ruído removido")
            else:
                self._update_progress(job, 70.0, "Pulando remoção de ruído")
            
            # Passo 5: Dynamic Range Compression (equaliza volume da fala)
            self._update_progress(job, 75.0, "Compressão dinâmica (equaliza voz)")
            audio = compress_dynamic_range(
                audio,
                threshold=-20.0,  # dB
                ratio=4.0,        # Compressão 4:1
                attack=5.0,       # ms
                release=50.0      # ms
            )
            
            # Passo 6: Normaliza volume
            if job.normalize_volume:
                self._update_progress(job, 80.0, "Normalizando volume")
                audio = pydub_normalize(audio)
                self._update_progress(job, 85.0, "Volume normalizado")
            else:
                self._update_progress(job, 85.0, "Pulando normalização de volume")
            
            # Salva arquivo processado com codec Opus (melhor para voz)
            self._update_progress(job, 90.0, "Exportando com codec Opus")
            
            # Força extensão .opus para garantir codec correto
            output_filename = f"{job.id}_normalized.opus"
            output_path = self.output_dir / output_filename
            
            # Exporta como Opus 64kbps mono (ideal para voz)
            audio.export(
                str(output_path),
                format="opus",
                codec="libopus",
                bitrate="64k",
                parameters=["-vbr", "on", "-compression_level", "10", "-application", "voip"]
            )
            
            # Atualiza job com resultado
            job.output_file = str(output_path)
            job.file_size_output = output_path.stat().st_size
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress = 100.0
            
            # Calcula redução de tamanho
            reduction = ((job.file_size_input - job.file_size_output) / job.file_size_input) * 100
            logger.info(
                f"Processamento concluído: {job.output_file} "
                f"(redução: {reduction:.1f}%)"
            )
            
            # 🗑️ Deleta arquivo de INPUT (mantém só o processado)
            try:
                if input_path.exists():
                    input_path.unlink()
                    logger.info(f"Arquivo de entrada deletado: {input_path}")
            except Exception as e:
                logger.warning(f"Erro ao deletar arquivo de entrada: {e}")
            
            return job
            
        except Exception as e:
            logger.error(f"Erro no processamento: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            
            # Tenta deletar input mesmo em caso de falha
            try:
                if Path(job.input_file).exists():
                    Path(job.input_file).unlink()
                    logger.info(f"Arquivo de entrada deletado após falha: {job.input_file}")
            except Exception as cleanup_error:
                logger.warning(f"Erro ao deletar arquivo após falha: {cleanup_error}")
            
            return job
    
    def _isolate_vocals(self, audio_path: Path, job: Job) -> AudioSegment:
        """
        Isola vocais usando Spleeter (Deezer AI)
        
        Usa modelo 2stems que separa em:
        - vocals: voz isolada  
        - accompaniment: instrumental
        
        Args:
            audio_path: Caminho do arquivo de áudio
            job: Job para atualizar progresso
            
        Returns:
            AudioSegment contendo apenas vocais
        """
        temp_output_dir = None
        
        try:
            import tempfile
            import shutil
            
            # Carrega Spleeter (lazy load)
            separator = get_spleeter_separator()
            
            # Cria diretório temporário para output do Spleeter
            temp_output_dir = tempfile.mkdtemp(prefix=f"spleeter_{job.id}_")
            
            self._update_progress(job, 11.0, "Preparando áudio")
            logger.info("🔄 Preparando áudio para Spleeter: %s", audio_path)
            
            # Spleeter aceita vários formatos via ffmpeg
            self._update_progress(job, 13.0, "Carregando modelo de IA")
            
            # Calcula estimativa (Spleeter é mais rápido que Demucs)
            audio_temp = AudioSegment.from_file(str(audio_path))
            duration_seconds = len(audio_temp) / 1000.0
            estimated_time = int(duration_seconds * 0.3)  # ~0.3s por segundo
            
            self._update_progress(job, 15.0, f"Separando voz (~{estimated_time}s)")
            logger.info("🎵 Processando com Spleeter")
            logger.info("   ├─ Duração: %.1fs", duration_seconds)
            logger.info("   └─ Tempo estimado: ~%ss", estimated_time)
            logger.info("⏳ Processando com IA (aguarde)...")
            
            import time
            start_time = time.time()
            
            # Separa vocais - Spleeter cria: {temp_dir}/{filename_sem_ext}/vocals.wav
            separator.separate_to_file(
                str(audio_path),
                temp_output_dir,
                codec='wav'
            )
            
            elapsed = time.time() - start_time
            logger.info("✨ Separação concluída em %.1fs!", elapsed)
            
            self._update_progress(job, 22.0, "Extraindo trilha de vocais")
            
            # Localiza arquivo de vocais
            audio_name = audio_path.stem
            vocals_path = Path(temp_output_dir) / audio_name / "vocals.wav"
            
            if not vocals_path.exists():
                raise FileNotFoundError(f"Arquivo de vocais não encontrado: {vocals_path}")
            
            self._update_progress(job, 24.0, "Finalizando isolamento")
            
            # Carrega vocais como AudioSegment
            vocals_audio = AudioSegment.from_wav(str(vocals_path))
            
            logger.info("✅ Voz isolada com sucesso usando Spleeter")
            return vocals_audio
                
        except Exception as exc:
            logger.error("❌ Erro ao isolar voz com Spleeter: %s", exc)
            logger.warning("Usando áudio original (sem isolamento)")
            return AudioSegment.from_file(str(audio_path))
            
        finally:
            # Remove diretório temporário completo
            if temp_output_dir and Path(temp_output_dir).exists():
                import shutil
                shutil.rmtree(temp_output_dir, ignore_errors=True)
                logger.info("🗑️ Removido diretório temporário: %s", temp_output_dir)
                logger.info(f"🗑️ Removido WAV temporário: {temp_wav_path}")
            if temp_vocals_path and Path(temp_vocals_path).exists():
                Path(temp_vocals_path).unlink()
                logger.info(f"🗑️ Removido vocals temporário: {temp_vocals_path}")
    
    def _remove_noise(self, audio: AudioSegment, job: Job) -> AudioSegment:
        """
        Remove ruído do áudio usando noisereduce
        
        Estratégia:
        1. Converte AudioSegment para numpy array
        2. Aplica noise reduction
        3. Converte de volta para AudioSegment
        """
        try:
            # Converte para numpy array
            samples = np.array(audio.get_array_of_samples())
            
            # Reshape para stereo se necessário
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Aplica noise reduction
            # stationary=True assume que o ruído é constante ao longo do áudio
            reduced_samples = nr.reduce_noise(
                y=samples,
                sr=audio.frame_rate,
                stationary=True,
                prop_decrease=0.8  # Reduz 80% do ruído detectado
            )
            
            # Converte de volta para AudioSegment
            reduced_audio = AudioSegment(
                reduced_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
            return reduced_audio
            
        except Exception as e:
            logger.warning(f"Erro na remoção de ruído, usando áudio original: {e}")
            return audio
    
    def _apply_highpass_filter(self, audio: AudioSegment, cutoff: int = 80) -> AudioSegment:
        """
        Aplica filtro high-pass para remover frequências baixas inaudíveis
        
        Args:
            audio: AudioSegment de entrada
            cutoff: Frequência de corte em Hz (padrão: 80Hz para voz)
            
        Returns:
            AudioSegment filtrado
        """
        try:
            # Converte para numpy array
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Normaliza para -1.0 a 1.0
            samples = samples / (2 ** (audio.sample_width * 8 - 1))
            
            # Design do filtro Butterworth high-pass (ordem 5)
            nyquist = audio.frame_rate / 2
            normal_cutoff = cutoff / nyquist
            b, a = signal.butter(5, normal_cutoff, btype='high', analog=False)
            
            # Aplica filtro
            filtered_samples = signal.filtfilt(b, a, samples)
            
            # Converte de volta para int
            filtered_samples = np.int16(filtered_samples * (2 ** (audio.sample_width * 8 - 1)))
            
            # Cria novo AudioSegment
            filtered_audio = AudioSegment(
                filtered_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
            return filtered_audio
            
        except Exception as e:
            logger.warning(f"Erro ao aplicar filtro high-pass, usando áudio original: {e}")
            return audio
    
    def get_file_path(self, job: Job) -> Optional[Path]:
        """Retorna caminho do arquivo processado se existir"""
        if job.output_file and Path(job.output_file).exists():
            return Path(job.output_file)
        return None


# Import necessário para datetime
from datetime import datetime
