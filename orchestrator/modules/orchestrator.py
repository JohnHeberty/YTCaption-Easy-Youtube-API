"""
Lógica de orquestração do pipeline completo
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from .models import (
    PipelineJob, 
    PipelineStatus, 
    StageStatus,
    PipelineStage
)
from .config import get_orchestrator_settings, get_microservice_config

logger = logging.getLogger(__name__)


class MicroserviceClient:
    """Cliente para comunicação com microserviços"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = get_microservice_config(service_name)
        self.base_url = self.config["url"]
        self.timeout = self.config["timeout"]
        self.endpoints = self.config["endpoints"]
    
    async def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submete job ao microserviço"""
        endpoint = self.endpoints.get("submit") or self.endpoints.get("process") or self.endpoints.get("download")
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"Submitting job to {self.service_name}: {url}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Consulta status do job"""
        endpoint = self.endpoints.get("status", f"/jobs/{job_id}")
        url = f"{self.base_url}{endpoint}".format(job_id=job_id)
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def check_health(self) -> bool:
        """Verifica saúde do microserviço"""
        endpoint = self.endpoints.get("health", "/health")
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for {self.service_name}: {str(e)}")
            return False


class PipelineOrchestrator:
    """Orquestrador do pipeline completo"""
    
    def __init__(self):
        self.settings = get_orchestrator_settings()
        self.video_client = MicroserviceClient("video-downloader")
        self.audio_client = MicroserviceClient("audio-normalization")
        self.transcription_client = MicroserviceClient("audio-transcriber")
        
        self.poll_interval = self.settings["poll_interval"]
        self.max_attempts = self.settings["max_poll_attempts"]
    
    async def check_services_health(self) -> Dict[str, str]:
        """Verifica saúde de todos os serviços"""
        results = {}
        
        for name, client in [
            ("video-downloader", self.video_client),
            ("audio-normalization", self.audio_client),
            ("audio-transcriber", self.transcription_client)
        ]:
            is_healthy = await client.check_health()
            results[name] = "healthy" if is_healthy else "unhealthy"
        
        return results
    
    async def execute_pipeline(self, job: PipelineJob) -> PipelineJob:
        """Executa pipeline completo"""
        try:
            logger.info(f"Starting pipeline for job {job.id}")
            
            # Estágio 1: Download do vídeo
            job.status = PipelineStatus.DOWNLOADING
            video_file = await self._execute_download(job)
            if not video_file:
                job.mark_as_failed("Download failed")
                return job
            
            # Estágio 2: Normalização de áudio
            job.status = PipelineStatus.NORMALIZING
            audio_file = await self._execute_normalization(job, video_file)
            if not audio_file:
                job.mark_as_failed("Audio normalization failed")
                return job
            
            job.audio_file = audio_file
            
            # Estágio 3: Transcrição
            job.status = PipelineStatus.TRANSCRIBING
            transcription = await self._execute_transcription(job, audio_file)
            if not transcription:
                job.mark_as_failed("Transcription failed")
                return job
            
            job.transcription_text = transcription.get("text")
            job.transcription_file = transcription.get("file")
            
            # Pipeline completo
            job.mark_as_completed()
            logger.info(f"Pipeline completed for job {job.id}")
            
            return job
            
        except Exception as e:
            logger.error(f"Pipeline failed for job {job.id}: {str(e)}")
            job.mark_as_failed(str(e))
            return job
    
    async def _execute_download(self, job: PipelineJob) -> Optional[str]:
        """Executa download do vídeo"""
        stage = job.download_stage
        stage.start()
        
        try:
            # Submete job ao video-downloader
            payload = {"url": job.youtube_url}
            response = await self.video_client.submit_job(payload)
            
            stage.job_id = response.get("job_id")
            logger.info(f"Video download job submitted: {stage.job_id}")
            
            # Polling do status
            video_file = await self._poll_job_status(
                client=self.video_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="output_file"
            )
            
            if video_file:
                stage.complete(video_file)
                job.update_progress()
                return video_file
            else:
                stage.fail("Download timeout or failed")
                return None
                
        except Exception as e:
            logger.error(f"Download stage failed: {str(e)}")
            stage.fail(str(e))
            return None
    
    async def _execute_normalization(self, job: PipelineJob, video_file: str) -> Optional[str]:
        """Executa normalização de áudio"""
        stage = job.normalization_stage
        stage.start()
        
        try:
            # Submete job ao audio-normalization
            payload = {
                "input_file": video_file,
                "remove_noise": job.remove_noise,
                "convert_to_mono": job.convert_to_mono,
                "sample_rate_16k": job.sample_rate_16k
            }
            response = await self.audio_client.submit_job(payload)
            
            stage.job_id = response.get("job_id")
            logger.info(f"Audio normalization job submitted: {stage.job_id}")
            
            # Polling do status
            audio_file = await self._poll_job_status(
                client=self.audio_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="output_file"
            )
            
            if audio_file:
                stage.complete(audio_file)
                job.update_progress()
                return audio_file
            else:
                stage.fail("Normalization timeout or failed")
                return None
                
        except Exception as e:
            logger.error(f"Normalization stage failed: {str(e)}")
            stage.fail(str(e))
            return None
    
    async def _execute_transcription(self, job: PipelineJob, audio_file: str) -> Optional[Dict[str, Any]]:
        """Executa transcrição de áudio"""
        stage = job.transcription_stage
        stage.start()
        
        try:
            # Submete job ao audio-transcriber
            payload = {
                "audio_file": audio_file,
                "language": job.language
            }
            response = await self.transcription_client.submit_job(payload)
            
            stage.job_id = response.get("job_id")
            logger.info(f"Transcription job submitted: {stage.job_id}")
            
            # Polling do status
            result = await self._poll_job_status(
                client=self.transcription_client,
                job_id=stage.job_id,
                stage=stage,
                output_key="transcription"
            )
            
            if result:
                output_file = result.get("file") or result.get("output_file")
                stage.complete(output_file)
                job.update_progress()
                return result
            else:
                stage.fail("Transcription timeout or failed")
                return None
                
        except Exception as e:
            logger.error(f"Transcription stage failed: {str(e)}")
            stage.fail(str(e))
            return None
    
    async def _poll_job_status(
        self, 
        client: MicroserviceClient,
        job_id: str,
        stage: PipelineStage,
        output_key: str
    ) -> Optional[Any]:
        """Faz polling do status do job até completar"""
        attempts = 0
        
        while attempts < self.max_attempts:
            try:
                status = await client.get_job_status(job_id)
                
                # Atualiza progresso
                if "progress" in status:
                    stage.progress = status["progress"]
                
                # Verifica se completou
                job_status = status.get("status", "").lower()
                
                if job_status in ["completed", "success"]:
                    logger.info(f"Job {job_id} completed")
                    return status.get(output_key) or status
                
                elif job_status in ["failed", "error"]:
                    error = status.get("error") or status.get("error_message", "Unknown error")
                    logger.error(f"Job {job_id} failed: {error}")
                    return None
                
                # Ainda processando
                await asyncio.sleep(self.poll_interval)
                attempts += 1
                
            except Exception as e:
                logger.error(f"Error polling job {job_id}: {str(e)}")
                await asyncio.sleep(self.poll_interval)
                attempts += 1
        
        logger.error(f"Job {job_id} timeout after {attempts} attempts")
        return None
