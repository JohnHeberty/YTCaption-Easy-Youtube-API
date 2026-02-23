"""
Shared module - Events, exceptions, validation, integration

Shared components used across the application.
"""

from .events import Event, EventType, EventPublisher, EventSubscriber
from .exceptions import (
    ErrorCode,
    EnhancedMakeVideoException,
    MakeVideoException,
    AudioProcessingException,
    VideoProcessingException,
    MicroserviceException,
    SystemException,
)
from .validation import (
    QueryValidator,
    CreateVideoRequestValidated,
    AudioFileValidator,
    VideoFileValidator,
)
# Domain Integration commented to avoid circular import
# Import directly: from app.shared.domain_integration import ...
# from .domain_integration import DomainJobProcessor, process_job_with_domain

__all__ = [
    # Events
    'Event',
    'EventType',
    'EventPublisher',
    'EventSubscriber',
    # Exceptions
    'ErrorCode',
    'EnhancedMakeVideoException',
    'MakeVideoException',
    'AudioProcessingException',
    'VideoProcessingException',
    'MicroserviceException',
    'SystemException',
    # Validation
    'QueryValidator',
    'CreateVideoRequestValidated',
    'AudioFileValidator',
    'VideoFileValidator',
    # Domain Integration - not exported to avoid circular import
    # 'DomainJobProcessor',
    # 'process_job_with_domain',
]
