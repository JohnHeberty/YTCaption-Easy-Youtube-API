"""Excecoes especificas do orchestrator.

Todas as excecoes herdam de OrchestratorError para permitir
captura generica quando necessario, mas tambem fornecem
tipos especificos para tratamento detalhado.
"""


class OrchestratorError(Exception):
    """Base para todas as excecoes do orchestrator.
    
    Attributes:
        message: Mensagem de erro
        error_code: Codigo de erro para identificacao
    """
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or "ORCHESTRATOR_ERROR"
        super().__init__(message)


class ValidationError(OrchestratorError):
    """Erro de validacao de dados de entrada.
    
    Levantado quando os dados da requisicao nao atendem
    aos requisitos esperados.
    
    Example:
        raise ValidationError("URL invalida", "INVALID_URL")
    """
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class JobCreationError(OrchestratorError):
    """Erro ao criar job.
    
    Levantado quando nao e possivel criar um novo job
    devido a problemas internos.
    """
    
    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(message, "JOB_CREATION_ERROR")


class RedisConnectionError(OrchestratorError):
    """Erro de conexao com Redis.
    
    Levantado quando nao e possivel conectar ou operar
    no Redis.
    """
    
    def __init__(self, message: str, redis_url: str = None):
        self.redis_url = redis_url
        super().__init__(message, "REDIS_CONNECTION_ERROR")


class PipelineExecutionError(OrchestratorError):
    """Erro na execucao do pipeline.
    
    Levantado quando uma etapa do pipeline falha.
    
    Attributes:
        stage: Nome do stage que falhou
    """
    
    def __init__(self, message: str, stage: str = None):
        self.stage = stage
        super().__init__(message, "PIPELINE_EXECUTION_ERROR")


class MicroserviceError(OrchestratorError):
    """Erro em comunicacao com microservico.
    
    Levantado quando um microservico retorna erro
    ou nao responde.
    
    Attributes:
        service_name: Nome do servico que falhou
        status_code: HTTP status code, se aplicavel
    """
    
    def __init__(
        self, 
        message: str, 
        service_name: str = None,
        status_code: int = None
    ):
        self.service_name = service_name
        self.status_code = status_code
        super().__init__(message, "MICROSERVICE_ERROR")


class CircuitBreakerOpenError(OrchestratorError):
    """Circuit breaker aberto.
    
    Levantado quando o circuit breaker esta aberto
    para um microservico.
    """
    
    def __init__(self, message: str, service_name: str = None):
        self.service_name = service_name
        super().__init__(message, "CIRCUIT_BREAKER_OPEN")
