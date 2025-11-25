"""
Store Redis para jobs e perfis de voz
"""
import asyncio
import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta

import redis
from redis import Redis

from .models import Job, VoiceProfile, JobStatus

logger = logging.getLogger(__name__)


class RedisJobStore:
    """Store Redis para jobs de dublagem/clonagem e perfis de voz"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self._cleanup_task = None
        
    async def start_cleanup_task(self):
        """Inicia task de limpeza automática de jobs expirados"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Cleanup task started")
    
    async def stop_cleanup_task(self):
        """Para task de limpeza"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Cleanup task stopped")
    
    async def _cleanup_loop(self):
        """Loop de limpeza automática (a cada 30 minutos)"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutos
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired(self):
        """Remove jobs e perfis expirados"""
        now = datetime.now()
        
        # Limpar jobs expirados
        job_keys = self.redis.keys("voice_job:*")
        expired_jobs = 0
        for key in job_keys:
            job_data = self.redis.get(key)
            if job_data:
                try:
                    job_dict = json.loads(job_data)
                    expires_at = datetime.fromisoformat(job_dict.get("expires_at", ""))
                    if now > expires_at:
                        self.redis.delete(key)
                        expired_jobs += 1
                except Exception as e:
                    logger.error(f"Error cleaning job {key}: {e}")
        
        # Limpar perfis de voz expirados
        profile_keys = self.redis.keys("voice_profile:*")
        expired_profiles = 0
        for key in profile_keys:
            profile_data = self.redis.get(key)
            if profile_data:
                try:
                    profile_dict = json.loads(profile_data)
                    expires_at = datetime.fromisoformat(profile_dict.get("expires_at", ""))
                    if now > expires_at:
                        self.redis.delete(key)
                        expired_profiles += 1
                except Exception as e:
                    logger.error(f"Error cleaning profile {key}: {e}")
        
        if expired_jobs > 0 or expired_profiles > 0:
            logger.info(f"Cleanup: removed {expired_jobs} jobs and {expired_profiles} voice profiles")
    
    # ===== JOBS =====
    
    def save_job(self, job: Job) -> None:
        """Salva job no Redis"""
        key = f"voice_job:{job.id}"
        self.redis.set(key, job.model_dump_json())
        logger.debug(f"Job saved: {job.id}")
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Recupera job do Redis"""
        key = f"voice_job:{job_id}"
        data = self.redis.get(key)
        if data:
            return Job.model_validate_json(data)
        return None
    
    def update_job(self, job: Job) -> None:
        """Atualiza job existente"""
        self.save_job(job)
        logger.debug(f"Job updated: {job.id}")
    
    def delete_job(self, job_id: str) -> bool:
        """Remove job do Redis"""
        key = f"voice_job:{job_id}"
        deleted = self.redis.delete(key)
        if deleted:
            logger.info(f"Job deleted: {job_id}")
        return deleted > 0
    
    def list_jobs(self, limit: int = 20) -> List[Job]:
        """Lista jobs recentes"""
        keys = self.redis.keys("voice_job:*")
        jobs = []
        
        for key in keys[:limit]:
            data = self.redis.get(key)
            if data:
                try:
                    job = Job.model_validate_json(data)
                    jobs.append(job)
                except Exception as e:
                    logger.error(f"Error parsing job {key}: {e}")
        
        # Ordena por data de criação (mais recentes primeiro)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
    
    # ===== VOICE PROFILES =====
    
    def save_voice_profile(self, profile: VoiceProfile) -> None:
        """Salva perfil de voz no Redis"""
        key = f"voice_profile:{profile.id}"
        self.redis.set(key, profile.model_dump_json())
        logger.info(f"Voice profile saved: {profile.id} ({profile.name})")
    
    def get_voice_profile(self, voice_id: str) -> Optional[VoiceProfile]:
        """Recupera perfil de voz do Redis"""
        key = f"voice_profile:{voice_id}"
        data = self.redis.get(key)
        if data:
            return VoiceProfile.model_validate_json(data)
        return None
    
    def update_voice_profile(self, profile: VoiceProfile) -> None:
        """Atualiza perfil de voz existente"""
        self.save_voice_profile(profile)
    
    def delete_voice_profile(self, voice_id: str) -> bool:
        """Remove perfil de voz do Redis"""
        key = f"voice_profile:{voice_id}"
        deleted = self.redis.delete(key)
        if deleted:
            logger.info(f"Voice profile deleted: {voice_id}")
        return deleted > 0
    
    def list_voice_profiles(self, limit: int = 100) -> List[VoiceProfile]:
        """Lista perfis de voz"""
        keys = self.redis.keys("voice_profile:*")
        profiles = []
        
        for key in keys[:limit]:
            data = self.redis.get(key)
            if data:
                try:
                    profile = VoiceProfile.model_validate_json(data)
                    if not profile.is_expired:  # Só retorna perfis válidos
                        profiles.append(profile)
                except Exception as e:
                    logger.error(f"Error parsing voice profile {key}: {e}")
        
        # Ordena por data de criação (mais recentes primeiro)
        profiles.sort(key=lambda p: p.created_at, reverse=True)
        return profiles[:limit]
    
    # ===== STATS =====
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do sistema"""
        job_keys = self.redis.keys("voice_job:*")
        profile_keys = self.redis.keys("voice_profile:*")
        
        jobs = []
        for key in job_keys:
            data = self.redis.get(key)
            if data:
                try:
                    jobs.append(Job.model_validate_json(data))
                except:
                    pass
        
        profiles = []
        for key in profile_keys:
            data = self.redis.get(key)
            if data:
                try:
                    profiles.append(VoiceProfile.model_validate_json(data))
                except:
                    pass
        
        # Conta por status
        job_stats = {
            "total": len(jobs),
            "queued": sum(1 for j in jobs if j.status == JobStatus.QUEUED),
            "processing": sum(1 for j in jobs if j.status == JobStatus.PROCESSING),
            "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
        }
        
        voice_stats = {
            "total": len(profiles),
            "active": sum(1 for p in profiles if not p.is_expired),
            "expired": sum(1 for p in profiles if p.is_expired),
            "total_usage": sum(p.usage_count for p in profiles),
        }
        
        return {
            "jobs": job_stats,
            "voice_profiles": voice_stats,
            "redis_keys": {
                "jobs": len(job_keys),
                "profiles": len(profile_keys),
            }
        }
