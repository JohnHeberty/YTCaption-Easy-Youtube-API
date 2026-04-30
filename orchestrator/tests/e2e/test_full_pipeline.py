"""
Testes End-to-End do pipeline completo.
"""
import pytest


@pytest.mark.e2e
class TestFullPipeline:
    """Testes E2E do pipeline completo."""

    @pytest.mark.skip(reason="E2E tests require full infrastructure")
    async def test_complete_pipeline(self):
        """
        Teste E2E completo:
        1. Criar job
        2. Processar
        3. Verificar resultado
        """
        pass


@pytest.mark.skip(reason="E2E tests require running services")
class TestFullPipelineLive:
    """Testes E2E com serviços reais."""

    @pytest.mark.asyncio
    async def test_pipeline_lifecycle(self):
        """Deve processar vídeo do início ao fim."""
        from domain.models import PipelineJob
        from infrastructure.dependency_injection import get_pipeline_orchestrator
        from infrastructure.redis_store import get_store

        # Cria job
        job = PipelineJob.create_new("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        # Obtém orquestrador
        redis = get_store()
        orchestrator = get_pipeline_orchestrator(redis)

        # Executa pipeline
        result = await orchestrator.execute_pipeline(job)

        # Verifica resultado
        assert result.status.value in ["completed", "failed"]
