"""
Interfaces abstratas para o orquestrador.

Define contratos que devem ser implementados pelos componentes,
permitindo injeção de dependência e testes unitários.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, Tuple


class MicroserviceClientInterface(ABC):
    """
    Interface base para clientes de microserviços.

    Todos os clientes de microserviços devem implementar esta interface
    para permitir mocking em testes e injeção de dependência.
    """

    @abstractmethod
    async def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submete um job para o microserviço.

        Args:
            payload: Dados do job a ser processado

        Returns:
            Dict[str, Any]: Resposta do serviço com job_id

        Raises:
            PipelineStageError: Se a submissão falhar
        """
        pass

    @abstractmethod
    async def submit_multipart(
        self, files: Dict[str, Any], data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submete arquivo via multipart/form-data.

        Args:
            files: Arquivos a serem enviados
            data: Dados adicionais do formulário

        Returns:
            Dict[str, Any]: Resposta do serviço

        Raises:
            PipelineStageError: Se a submissão falhar
        """
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um job.

        Args:
            job_id: ID do job

        Returns:
            Optional[Dict[str, Any]]: Status do job ou None se não encontrado

        Raises:
            PipelineStageError: Se a consulta falhar
        """
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Verifica saúde do serviço.

        Returns:
            Dict[str, Any]: Status de saúde do serviço
        """
        pass

    @abstractmethod
    async def download_file(self, job_id: str) -> Tuple[bytes, str]:
        """
        Baixa resultado do job.

        Args:
            job_id: ID do job

        Returns:
            Tuple[bytes, str]: Conteúdo do arquivo e nome do arquivo

        Raises:
            PipelineStageError: Se o download falhar
        """
        pass


class PipelineStageInterface(ABC):
    """
    Interface para estágios do pipeline.

    Cada estágio do pipeline (download, normalization, transcription)
    deve implementar esta interface para ser orquestrado.
    """

    @abstractmethod
    async def execute(self, job: Any) -> Any:
        """
        Executa o estágio.

        Args:
            job: Job do pipeline em processamento

        Returns:
            Any: Resultado da execução

        Raises:
            PipelineStageError: Se a execução falhar
        """
        pass

    @abstractmethod
    async def rollback(self, job: Any) -> None:
        """
        Reverte em caso de falha.

        Args:
            job: Job do pipeline que falhou

        Raises:
            PipelineStageError: Se o rollback falhar
        """
        pass


class HealthCheckable(Protocol):
    """Protocol para serviços que podem ser verificados."""

    async def check_health(self) -> Dict[str, Any]:
        """
        Verifica saúde do serviço.

        Returns:
            Dict[str, Any]: Status de saúde
        """
        ...


class CircuitBreakerInterface(ABC):
    """Interface para Circuit Breaker."""

    @abstractmethod
    async def call(self, func: callable, *args: Any, **kwargs: Any) -> Any:
        """
        Executa função com proteção do circuit breaker.

        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Any: Resultado da função

        Raises:
            CircuitBreakerOpenError: Se o circuito estiver aberto
        """
        pass

    @abstractmethod
    def get_state(self) -> str:
        """
        Retorna estado atual do circuit breaker.

        Returns:
            str: Estado atual (CLOSED, OPEN, HALF_OPEN)
        """
        pass
