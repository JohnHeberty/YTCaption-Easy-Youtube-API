"""
Shared models for all microservices

HealthStatus is defined here. The canonical job models (JobStatus, StandardJob)
live in common.job_utils.models.
"""
from .base import HealthStatus

__all__ = ['HealthStatus']
