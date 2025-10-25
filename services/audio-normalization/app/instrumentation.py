"""
Instrumentação distribuída com OpenTelemetry
Fornece rastreamento de requests, métricas e logs estruturados
"""
import os
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager

from opentelemetry import trace, metrics, baggage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.trace.status import Status, StatusCode

from app.config import AppSettings
from app.logging_config import create_logger

logger = create_logger(__name__)


class DistributedTracing:
    """Gerenciador de rastreamento distribuído"""
    
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        self._initialized = False
        
        # Métricas customizadas
        self.request_duration_histogram = None
        self.request_counter = None
        self.error_counter = None
        self.processing_gauge = None
    
    def initialize(self) -> bool:
        """Inicializa instrumentação distribuída"""
        try:
            # Configura resource para identificar o serviço
            resource = Resource.create({
                "service.name": "audio-normalization",
                "service.version": "1.0.0",
                "service.environment": self.settings.environment,
                "service.instance.id": os.getenv("HOSTNAME", "local")
            })
            
            # Configura tracer
            self._setup_tracing(resource)
            
            # Configura métricas
            self._setup_metrics(resource)
            
            # Configura propagadores
            set_global_textmap(B3MultiFormat())
            
            # Instrumenta bibliotecas automaticamente
            self._setup_auto_instrumentation()
            
            self._initialized = True
            logger.info("Distributed tracing initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize distributed tracing: {e}")
            return False
    
    def _setup_tracing(self, resource: Resource):
        """Configura sistema de tracing"""
        # Provider de traces
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)
        
        # Exportador Jaeger (se configurado)
        jaeger_endpoint = self.settings.monitoring.jaeger_endpoint
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split("://")[1].split(":")[0],
                agent_port=int(jaeger_endpoint.split(":")[-1]),
            )
            
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace_provider.add_span_processor(span_processor)
        
        # Cria tracer
        self.tracer = trace.get_tracer(__name__)
    
    def _setup_metrics(self, resource: Resource):
        """Configura sistema de métricas"""
        # Provider de métricas
        metric_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)
        
        # Cria meter
        self.meter = metrics.get_meter(__name__)
        
        # Define métricas customizadas
        self.request_duration_histogram = self.meter.create_histogram(
            name="audio_processing_duration_seconds",
            description="Duration of audio processing operations",
            unit="s"
        )
        
        self.request_counter = self.meter.create_counter(
            name="audio_requests_total",
            description="Total number of audio processing requests"
        )
        
        self.error_counter = self.meter.create_counter(
            name="audio_errors_total", 
            description="Total number of processing errors"
        )
        
        self.processing_gauge = self.meter.create_up_down_counter(
            name="audio_processing_active",
            description="Number of audio files currently being processed"
        )
    
    def _setup_auto_instrumentation(self):
        """Configura instrumentação automática"""
        try:
            # Instrumenta Redis
            RedisInstrumentor().instrument()
            
            # Instrumenta requests HTTP
            RequestsInstrumentor().instrument()
            
            logger.info("Auto-instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to setup auto-instrumentation: {e}")
    
    @contextmanager
    def trace_operation(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager para rastreamento de operações"""
        if not self._initialized or not self.tracer:
            yield None
            return
        
        with self.tracer.start_as_current_span(operation_name) as span:
            try:
                # Adiciona atributos
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Adiciona informações do baggage
                baggage_items = baggage.get_all()
                for key, value in baggage_items.items():
                    span.set_attribute(f"baggage.{key}", value)
                
                yield span
                
                # Marca como sucesso
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                # Marca erro no span
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def trace_function(self, operation_name: Optional[str] = None, record_metrics: bool = True):
        """Decorator para rastreamento automático de funções"""
        def decorator(func: Callable) -> Callable:
            func_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return await self._trace_async_function(func, func_name, record_metrics, *args, **kwargs)
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    return self._trace_sync_function(func, func_name, record_metrics, *args, **kwargs)
                return sync_wrapper
                
        return decorator
    
    async def _trace_async_function(self, func: Callable, func_name: str, record_metrics: bool, *args, **kwargs):
        """Rastreia função assíncrona"""
        start_time = time.time()
        
        attributes = {
            "function.name": func_name,
            "function.module": func.__module__
        }
        
        with self.trace_operation(func_name, attributes) as span:
            try:
                # Incrementa contador de requests
                if record_metrics and self.request_counter:
                    self.request_counter.add(1, {"operation": func_name})
                
                # Incrementa gauge de processamento ativo
                if record_metrics and self.processing_gauge:
                    self.processing_gauge.add(1, {"operation": func_name})
                
                result = await func(*args, **kwargs)
                
                # Adiciona informações do resultado se disponível
                if hasattr(result, '__dict__') and span:
                    if hasattr(result, 'success'):
                        span.set_attribute("result.success", result.success)
                
                return result
                
            except Exception as e:
                # Registra erro nas métricas
                if record_metrics and self.error_counter:
                    self.error_counter.add(1, {
                        "operation": func_name,
                        "error_type": type(e).__name__
                    })
                raise
                
            finally:
                # Registra duração
                duration = time.time() - start_time
                
                if record_metrics and self.request_duration_histogram:
                    self.request_duration_histogram.record(duration, {"operation": func_name})
                
                # Decrementa gauge de processamento ativo
                if record_metrics and self.processing_gauge:
                    self.processing_gauge.add(-1, {"operation": func_name})
    
    def _trace_sync_function(self, func: Callable, func_name: str, record_metrics: bool, *args, **kwargs):
        """Rastreia função síncrona"""
        start_time = time.time()
        
        attributes = {
            "function.name": func_name,
            "function.module": func.__module__
        }
        
        with self.trace_operation(func_name, attributes) as span:
            try:
                # Incrementa contador de requests
                if record_metrics and self.request_counter:
                    self.request_counter.add(1, {"operation": func_name})
                
                result = func(*args, **kwargs)
                
                # Adiciona informações do resultado se disponível
                if hasattr(result, '__dict__') and span:
                    if hasattr(result, 'success'):
                        span.set_attribute("result.success", result.success)
                
                return result
                
            except Exception as e:
                # Registra erro nas métricas
                if record_metrics and self.error_counter:
                    self.error_counter.add(1, {
                        "operation": func_name,
                        "error_type": type(e).__name__
                    })
                raise
                
            finally:
                # Registra duração
                duration = time.time() - start_time
                
                if record_metrics and self.request_duration_histogram:
                    self.request_duration_histogram.record(duration, {"operation": func_name})
    
    def add_baggage(self, key: str, value: str):
        """Adiciona item ao baggage para propagação"""
        baggage.set_baggage(key, value)
    
    def get_trace_context(self) -> Dict[str, str]:
        """Obtém contexto de trace para propagação manual"""
        if not self._initialized:
            return {}
        
        from opentelemetry.propagate import inject
        carrier = {}
        inject(carrier)
        return carrier
    
    def instrument_fastapi_app(self, app):
        """Instrumenta aplicação FastAPI"""
        if not self._initialized:
            logger.warning("Tracing not initialized, skipping FastAPI instrumentation")
            return
        
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")


# Instância global
_tracing_instance: Optional[DistributedTracing] = None


def get_tracing() -> DistributedTracing:
    """Obtém instância global de tracing"""
    global _tracing_instance
    
    if _tracing_instance is None:
        from app.config import get_settings
        settings = get_settings()
        _tracing_instance = DistributedTracing(settings)
        _tracing_instance.initialize()
    
    return _tracing_instance


def trace_operation(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """Decorator simplificado para rastreamento de operações"""
    tracing = get_tracing()
    return tracing.trace_operation(operation_name, attributes)


def trace_function(operation_name: Optional[str] = None, record_metrics: bool = True):
    """Decorator simplificado para rastreamento de funções"""
    tracing = get_tracing()
    return tracing.trace_function(operation_name, record_metrics)


# Importa asyncio aqui para evitar import circular
import asyncio