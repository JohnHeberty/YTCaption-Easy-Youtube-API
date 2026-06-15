"""
Shared models for all microservices

The canonical job models now live in common.job_utils.models.
This module re-exports BaseJob/JobStatus/HealthStatus for backward
compatibility with existing imports.
"""
from .base import BaseJob, HealthStatus
from common.job_utils.models import JobStatus as JobStatus

__all__ = ['BaseJob', 'JobStatus', 'HealthStatus']
