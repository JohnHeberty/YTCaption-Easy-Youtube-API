import os
import asyncio
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize
from .models import Job, JobStatus


class AudioProcessor:
    def __init__(self):
        self.job_store = None  # Will be injected
    
    async def process_audio_job(self, job: Job):
        """Processa um job de áudio"""
        try:
            # Atualiza status para processando
            job.status = JobStatus.PROCESSING
            if self.job_store:
                self.job_store.update_job(job)
            
            # Carrega arquivo de áudio
            audio = AudioSegment.from_file(job.input_file)
            
            # Atualiza progresso
            job.progress = 25.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Processa baseado na operação
            if job.operation == "normalize":
                processed_audio = normalize(audio)
            else:
                processed_audio = audio
            
            # Atualiza progresso
            job.progress = 75.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Salva arquivo processado
            output_dir = Path("./processed")
            output_dir.mkdir(exist_ok=True)
            
            output_path = output_dir / f"{job.id}_processed.wav"
            processed_audio.export(str(output_path), format="wav")
            
            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.file_size_output = output_path.stat().st_size
            
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