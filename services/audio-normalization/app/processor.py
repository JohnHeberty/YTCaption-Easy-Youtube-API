    
import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from datetime import datetime
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize
import logging
from pathlib import Path
from typing import Optional
    return _openunmix_model


class AudioProcessor:
    """Processador de áudio para normalização"""
    
    def __init__(self, output_dir: str = None, temp_dir: str = None) -> None:
        """
        Inicializa o processador de áudio.
        Args:
            output_dir (str, opcional): Diretório de saída dos arquivos processados.
            temp_dir (str, opcional): Diretório para arquivos temporários.
        """
        self.output_dir = Path(output_dir or os.getenv('OUTPUT_DIR', './processed'))
        self.output_dir.mkdir(exist_ok=True)
import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize
from .models import Job, JobStatus

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Importa OpenUnmix apenas quando necessário (lazy load)
_openunmix_model = None

        self.temp_dir = Path(temp_dir or os.getenv('TEMP_DIR', './temp'))
        self.temp_dir.mkdir(exist_ok=True)
        # Referência para o job store será injetada
        self.job_store = None
    
    def _update_progress(self, job: Job, progress: float, message: str = "") -> None:
        """
        Atualiza o progresso do job e registra no log.
        Args:
            job (Job): Instância do job.
            progress (float): Progresso percentual.
            message (str): Mensagem adicional.
        """
        job.progress = min(progress, 99.9)
        if self.job_store:
            self.job_store.update_job(job)
        logger.info("Job %s: %.1f%% - %s", job.id, progress, message)
    
    def process_audio(self, job: Job) -> Job:
        """
        Processa o áudio conforme parâmetros do job.
        Args:
            job (Job): Instância do job.
        Returns:
            Job: Job atualizado após processamento.
        """
    # Processa áudio conforme parâmetros do job. Só executa operações ativas, pula as desativadas.
        try:
            job.status = JobStatus.PROCESSING
            self._update_progress(job, 5.0, "Iniciando processamento")

            input_path = Path(job.input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {job.input_file}")

            job.file_size_input = input_path.stat().st_size

            # Se todos os parâmetros estiverem desativados, pula processamento
            if not any([
                job.isolate_vocals,
                job.remove_noise,
                job.normalize_volume,
                job.convert_to_mono,
                job.apply_highpass_filter,
                job.set_sample_rate_16k
            ]):
                self._update_progress(job, 95.0, "Nenhuma operação solicitada, pulando processamento")
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                job.progress = 100.0
                job.output_file = None
                job.file_size_output = None
                return job

            # Processamento condicional conforme parâmetros
            audio = AudioSegment.from_file(input_path)
            if audio is None:
                raise RuntimeError(f"Falha ao carregar arquivo de áudio: {input_path}")

            # Executa operações conforme parâmetros
            if job.isolate_vocals:
                audio = self._isolate_vocals(input_path, job)
                self._update_progress(job, 20.0, "Vocais isolados")

            if job.remove_noise:
                audio = self._remove_noise(audio, job)
                self._update_progress(job, 40.0, "Ruído removido")

            if job.normalize_volume:
                audio = pydub_normalize(audio)
                self._update_progress(job, 60.0, "Volume normalizado")

            if job.convert_to_mono:
                audio = audio.set_channels(1)
                self._update_progress(job, 70.0, "Convertido para mono")

            if job.apply_highpass_filter:
                audio = self._apply_highpass_filter(audio, job)
                self._update_progress(job, 80.0, "Filtro highpass aplicado")

            if job.set_sample_rate_16k:
                audio = audio.set_frame_rate(16000)
                self._update_progress(job, 90.0, "Sample rate ajustado para 16kHz")

            # Exporta arquivo processado
            output_path = self.output_dir / f"{job.id}.opus"
            audio.export(output_path, format="opus")
            job.output_file = str(output_path)
            job.file_size_output = output_path.stat().st_size
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress = 100.0
            self._update_progress(job, 100.0, "Processamento concluído")
            return job
        except (FileNotFoundError, RuntimeError, OSError, ValueError) as e:
            logger.error("Erro no processamento: %s", e)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            try:
                if Path(job.input_file).exists():
                    Path(job.input_file).unlink()
                    logger.info("Arquivo de entrada deletado após falha: %s", job.input_file)
            except OSError as cleanup_error:
                logger.warning("Erro ao deletar arquivo após falha: %s", cleanup_error)
            return job
    
    def _isolate_vocals(self, audio_path: Path, job: Job) -> AudioSegment:
        """
        Isola vocais usando OpenUnmix.
        Args:
            audio_path (Path): Caminho do arquivo de áudio.
            job (Job): Instância do job.
        Returns:
            AudioSegment: Segmento de áudio contendo apenas vocais.
        """
        """
        Isola vocais usando OpenUnmix (mais leve e rápido)
        
        Args:
            audio_path: Caminho do arquivo de áudio
            job: Job para atualizar progresso
            
        Returns:
            AudioSegment contendo apenas vocais
        """
        temp_wav_path = None
        temp_vocals_path = None
        temp_dir = os.getenv('TEMP_DIR', './temp')
        
        try:
            import torch
            import torchaudio
            
            # Carrega OpenUnmix (lazy load)
            model = get_openunmix_model()
            
            # Converte para WAV se necessário
            self._update_progress(job, 11.0, "Convertendo para formato compatível")
            logger.info("🔄 Carregando %s para processamento", audio_path.suffix)
            
            audio_temp = AudioSegment.from_file(str(audio_path))
            temp_wav_path = os.path.join(temp_dir, f"{job.id}_input.wav")
            audio_temp.export(temp_wav_path, format='wav')
            
            logger.info("� WAV temporário criado: %s", temp_wav_path)
            
            # Carrega WAV com torchaudio
            self._update_progress(job, 13.0, "Carregando áudio em memória")
            wav, sr = torchaudio.load(temp_wav_path)
            
            # Calcula estimativa (OpenUnmix é rápido!)
            duration_seconds = wav.shape[1] / sr
            estimated_time = int(duration_seconds * 0.2)  # ~0.2s por segundo
            
            self._update_progress(job, 15.0, f"Separando voz com IA (~{estimated_time}s)")
            logger.info("🎵 Aplicando OpenUnmix no áudio")
            logger.info("   ├─ Sample rate: %sHz", sr)
            logger.info("   ├─ Shape: %s", wav.shape)
            logger.info("   ├─ Duração: %.1fs", duration_seconds)
            logger.info("   └─ Tempo estimado: ~%ss", estimated_time)
            logger.info("⏳ Processando com IA (aguarde)...")
            
            import time
            start_time = time.time()
            
            # OpenUnmix espera formato: [batch, channels, time]
            if wav.dim() == 2:
                wav = wav.unsqueeze(0)  # Adiciona batch dimension
            
            # Aplica modelo OpenUnmix
            with torch.no_grad():
                estimates = model(wav)
                # estimates tem formato: {target_name: tensor}
                vocals = estimates['vocals'].squeeze(0)  # Remove batch dimension
            
            elapsed = time.time() - start_time
            logger.info("✨ Separação concluída em %.1fs!", elapsed)
            
            self._update_progress(job, 22.0, "Extraindo trilha de vocais")
            
            # Salva vocais
            temp_vocals_path = os.path.join(temp_dir, f"{job.id}_vocals.wav")
            torchaudio.save(temp_vocals_path, vocals, sr)
            
            logger.info("🎤 Vocais extraídos, salvando WAV temporário")
            self._update_progress(job, 24.0, "Finalizando isolamento")
            
            # Carrega como AudioSegment
            vocals_audio = AudioSegment.from_wav(temp_vocals_path)
            
            logger.info("✅ Voz isolada com sucesso usando OpenUnmix")
            return vocals_audio
                
        except (RuntimeError, ValueError, OSError) as exc:
            logger.error("❌ Erro ao isolar voz com OpenUnmix: %s", exc)
            logger.warning("Usando áudio original (sem isolamento)")
            return AudioSegment.from_file(str(audio_path))
            
        finally:
            # Remove arquivos temporários
            if temp_wav_path and Path(temp_wav_path).exists():
                Path(temp_wav_path).unlink()
                logger.info("🗑️ Removido WAV temporário: %s", temp_wav_path)
            if temp_vocals_path and Path(temp_vocals_path).exists():
                Path(temp_vocals_path).unlink()
                logger.info("🗑️ Removido vocals temporário: %s", temp_vocals_path)
    
    def _remove_noise(self, audio: AudioSegment, job: Job = None) -> AudioSegment:
        """
        Remove ruído do áudio usando noisereduce.
        Args:
            audio (AudioSegment): Segmento de áudio de entrada.
            job (Job): Instância do job.
        Returns:
            AudioSegment: Segmento de áudio com ruído reduzido.
        """
        """
        Remove ruído do áudio usando noisereduce
        
        Estratégia:
        1. Converte AudioSegment para numpy array
        2. Aplica noise reduction
        3. Converte de volta para AudioSegment
        """
        try:
            import numpy as np
            import noisereduce as nr
            # Converte para numpy array
            samples = np.array(audio.get_array_of_samples())
            # Reshape para stereo se necessário
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            # Aplica noise reduction
            reduced_samples = nr.reduce_noise(
                y=samples,
                sr=audio.frame_rate,
                stationary=True,
                prop_decrease=0.8
            )
            # Converte de volta para AudioSegment
            reduced_audio = AudioSegment(
                reduced_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            return reduced_audio
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("Erro na remoção de ruído, usando áudio original: %s", e)
            return audio
    
    def _apply_highpass_filter(self, audio: AudioSegment, cutoff: int = 80) -> AudioSegment:
        """
        Aplica filtro high-pass para remover frequências baixas.
        Args:
            audio (AudioSegment): Segmento de áudio de entrada.
            cutoff (int): Frequência de corte em Hz.
        Returns:
            AudioSegment: Segmento de áudio filtrado.
        """
        """
        Aplica filtro high-pass para remover frequências baixas inaudíveis
        
        Args:
            audio: AudioSegment de entrada
            cutoff: Frequência de corte em Hz (padrão: 80Hz para voz)
            
        Returns:
            AudioSegment filtrado
        """
        try:
            import numpy as np
            from scipy import signal
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
            filtered_samples = np.nan_to_num(filtered_samples, nan=0.0, posinf=0.0, neginf=0.0)
            filtered_samples = np.int16(filtered_samples * (2 ** (audio.sample_width * 8 - 1)))
            filtered_audio = AudioSegment(
                filtered_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            return filtered_audio
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("Erro ao aplicar filtro high-pass, usando áudio original: %s", e)
            return audio
    
    def get_file_path(self, job: Job) -> Optional[Path]:
        """
        Retorna caminho do arquivo processado se existir.
        Args:
            job (Job): Instância do job.
        Returns:
            Optional[Path]: Caminho do arquivo ou None.
        """
        """Retorna caminho do arquivo processado se existir"""
        if job.output_file and Path(job.output_file).exists():
            return Path(job.output_file)
        return None


