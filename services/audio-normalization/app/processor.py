import os
import asyncio
import tempfile
import numpy as np
from datetime import datetime
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.effects import high_pass_filter
import noisereduce as nr
import soundfile as sf
import librosa
from .models import Job, JobStatus

# Para isolamento vocal com openunmix
try:
    import torch
    import openunmix
    OPENUNMIX_AVAILABLE = True
except ImportError:
    OPENUNMIX_AVAILABLE = False
    print("⚠️ OpenUnmix não disponível. Isolamento vocal será desabilitado.")


class AudioProcessor:
    def __init__(self):
        self.job_store = None  # Will be injected
        self._openunmix_model = None
    
    def _load_openunmix_model(self):
        """Carrega modelo openunmix para isolamento vocal"""
        if not OPENUNMIX_AVAILABLE:
            raise Exception("OpenUnmix não está disponível")
            
        if self._openunmix_model is None:
            print("🔄 Carregando modelo OpenUnmix...")
            self._openunmix_model = openunmix.load_model(device='cpu')
            print("✅ Modelo OpenUnmix carregado")
        return self._openunmix_model
    
    async def process_audio_job(self, job: Job):
        """Processa um job de áudio com operações condicionais"""
        try:
            # Atualiza status para processando
            job.status = JobStatus.PROCESSING
            if self.job_store:
                self.job_store.update_job(job)
            
            # Carrega arquivo de áudio
            print(f"🔄 Carregando arquivo: {job.input_file}")
            audio = AudioSegment.from_file(job.input_file)
            
            # Verifica se alguma operação foi solicitada
            any_operation = (job.remove_noise or job.convert_to_mono or 
                           job.apply_highpass_filter or job.set_sample_rate_16k or 
                           job.isolate_vocals)
            
            if not any_operation:
                print("ℹ️ Nenhuma operação solicitada - salvando arquivo original")
                job.progress = 50.0
                if self.job_store:
                    self.job_store.update_job(job)
            else:
                print(f"🔄 Aplicando operações: {job.processing_operations}")
                
                # Progresso inicial
                job.progress = 10.0
                if self.job_store:
                    self.job_store.update_job(job)
                
                # Aplicar operações condicionalmente
                processed_audio = await self._apply_processing_operations(audio, job)
                audio = processed_audio
            
            # Salva arquivo processado
            output_dir = Path("./processed")
            output_dir.mkdir(exist_ok=True)
            
            # Nome do arquivo baseado nas operações
            operations_suffix = f"_{job.processing_operations}" if job.processing_operations != "none" else ""
            output_path = output_dir / f"{job.id}{operations_suffix}.wav"
            
            print(f"💾 Salvando arquivo processado: {output_path}")
            audio.export(str(output_path), format="wav")
            
            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.file_size_output = output_path.stat().st_size
            job.completed_at = datetime.now()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            print(f"✅ Job {job.id} processado com sucesso")
            
        except Exception as e:
            # Marca job como falhou
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            
            if self.job_store:
                self.job_store.update_job(job)
            
            print(f"❌ Job {job.id} falhou: {e}")
    
    async def _apply_processing_operations(self, audio: AudioSegment, job: Job) -> AudioSegment:
        """Aplica operações de processamento condicionalmente"""
        progress_step = 80.0 / sum([
            job.remove_noise, job.convert_to_mono, job.apply_highpass_filter,
            job.set_sample_rate_16k, job.isolate_vocals
        ])
        current_progress = 10.0
        
        # 1. Isolamento vocal (primeiro, pois pode afetar outras operações)
        if job.isolate_vocals:
            print("🎤 Aplicando isolamento vocal...")
            audio = await self._isolate_vocals(audio)
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
        
        # 2. Remoção de ruído
        if job.remove_noise:
            print("🔇 Removendo ruído...")
            audio = await self._remove_noise(audio)
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
        
        # 3. Converter para mono
        if job.convert_to_mono:
            print("📻 Convertendo para mono...")
            audio = audio.set_channels(1)
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
        
        # 4. Aplicar filtro high-pass
        if job.apply_highpass_filter:
            print("🔊 Aplicando filtro high-pass...")
            audio = await self._apply_highpass_filter(audio)
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
        
        # 5. Reduzir sample rate para 16kHz
        if job.set_sample_rate_16k:
            print("📡 Reduzindo sample rate para 16kHz...")
            audio = audio.set_frame_rate(16000)
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
        
        return audio
    
    async def _isolate_vocals(self, audio: AudioSegment) -> AudioSegment:
        """Isola vocais usando OpenUnmix"""
        if not OPENUNMIX_AVAILABLE:
            print("⚠️ OpenUnmix não disponível - pulando isolamento vocal")
            return audio
        
        try:
            # Converte para numpy array
            samples = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Converte para float32 e normaliza
            samples = samples.astype(np.float32) / (2**15)
            
            # Se for mono, duplica para stereo (openunmix precisa de stereo)
            if len(samples.shape) == 1:
                samples = np.column_stack((samples, samples))
            
            # Aplica openunmix
            model = self._load_openunmix_model()
            
            # Converte para tensor
            audio_tensor = torch.from_numpy(samples.T).unsqueeze(0)
            
            with torch.no_grad():
                estimates = model(audio_tensor)
                vocals = estimates['vocals'].squeeze(0).cpu().numpy()
            
            # Converte de volta para pydub
            vocals = vocals.T
            if vocals.shape[1] == 2:
                vocals = vocals.flatten()
            
            # Normaliza e converte para int16
            vocals = (vocals * 2**15).astype(np.int16)
            
            # Cria novo AudioSegment
            processed_audio = AudioSegment(
                vocals.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=2,
                channels=1 if len(vocals.shape) == 1 else 2
            )
            
            return processed_audio
            
        except Exception as e:
            print(f"⚠️ Erro no isolamento vocal: {e}")
            return audio
    
    async def _remove_noise(self, audio: AudioSegment) -> AudioSegment:
        """Remove ruído usando noisereduce"""
        try:
            # Converte para numpy
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Normaliza
            samples = samples / (2**15)
            
            # Aplica redução de ruído
            reduced_noise = nr.reduce_noise(
                y=samples, 
                sr=audio.frame_rate,
                stationary=False,
                prop_decrease=0.8
            )
            
            # Converte de volta
            reduced_noise = (reduced_noise * 2**15).astype(np.int16)
            
            # Cria AudioSegment
            if len(reduced_noise.shape) == 2:
                reduced_noise = reduced_noise.flatten()
            
            processed_audio = AudioSegment(
                reduced_noise.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=2,
                channels=audio.channels
            )
            
            return processed_audio
            
        except Exception as e:
            print(f"⚠️ Erro na remoção de ruído: {e}")
            return audio
    
    async def _apply_highpass_filter(self, audio: AudioSegment) -> AudioSegment:
        """Aplica filtro high-pass"""
        try:
            # Frequência de corte: 80Hz (remove frequências muito baixas)
            cutoff_freq = 80
            return high_pass_filter(audio, cutoff_freq)
        except Exception as e:
            print(f"⚠️ Erro no filtro high-pass: {e}")
            return audio