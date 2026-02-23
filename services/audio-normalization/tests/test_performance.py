"""
Testes de carga e performance
"""
import pytest
import asyncio
import time
import concurrent.futures
from statistics import mean, median
from pathlib import Path
import tempfile

from app.models import Job, JobStatus
from app.security_validator import RateLimiter, ValidationMiddleware


class TestPerformance:
    """Testes de performance e carga"""
    
    @pytest.mark.performance
    async def test_concurrent_job_creation(self):
        """Testa criação concorrente de jobs"""
        def create_job(i):
            """Função auxiliar para criar job"""
            start_time = time.time()
            job = Job.create_new(
                input_file=f"/tmp/test_{i}.mp3",
                remove_noise=True,
                normalize_volume=True
            )
            creation_time = time.time() - start_time
            return job.id, creation_time
        
        # Cria jobs concorrentemente
        num_jobs = 100
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_job, i) for i in range(num_jobs)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verifica resultados
        job_ids = [result[0] for result in results]
        creation_times = [result[1] for result in results]
        
        # Todos os jobs devem ter IDs únicos (neste caso, arquivos diferentes)
        assert len(set(job_ids)) == num_jobs
        
        # Performance: criação deve ser rápida (< 10ms em média)
        avg_time = mean(creation_times)
        assert avg_time < 0.01, f"Job creation too slow: {avg_time:.4f}s average"
        
        print(f"Job creation performance: avg={avg_time:.4f}s, median={median(creation_times):.4f}s")
    
    @pytest.mark.performance
    async def test_rate_limiter_performance(self):
        """Testa performance do rate limiter sob carga"""
        limiter = RateLimiter(max_requests=1000, window_seconds=60)
        
        async def make_requests(client_id, num_requests):
            """Faz múltiplas requests para um cliente"""
            start_time = time.time()
            results = []
            
            for _ in range(num_requests):
                request_start = time.time()
                allowed = await limiter.is_allowed(client_id)
                request_time = time.time() - request_start
                results.append((allowed, request_time))
            
            total_time = time.time() - start_time
            return client_id, results, total_time
        
        # Testa com múltiplos clientes
        num_clients = 10
        requests_per_client = 50
        
        tasks = [
            make_requests(f"client_{i}", requests_per_client) 
            for i in range(num_clients)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Analisa performance
        all_request_times = []
        for client_id, client_results, total_time in results:
            request_times = [rt for _, rt in client_results]
            all_request_times.extend(request_times)
            
            # Cada cliente deve processar requests em tempo razoável
            assert total_time < 1.0, f"Client {client_id} too slow: {total_time:.4f}s"
        
        # Performance geral do rate limiter
        avg_request_time = mean(all_request_times)
        assert avg_request_time < 0.001, f"Rate limiter too slow: {avg_request_time:.4f}s average"
        
        print(f"Rate limiter performance: avg={avg_request_time:.6f}s per request")
    
    @pytest.mark.performance
    def test_job_store_operations_performance(self, job_store):
        """Testa performance de operações do job store"""
        num_operations = 100
        
        # Teste de salvamento
        jobs = []
        save_times = []
        
        for i in range(num_operations):
            job = Job.create_new(
                input_file=f"/tmp/perf_test_{i}.mp3",
                remove_noise=True
            )
            jobs.append(job)
            
            start_time = time.time()
            job_store.save_job(job)
            save_time = time.time() - start_time
            save_times.append(save_time)
        
        # Teste de recuperação
        retrieve_times = []
        
        for job in jobs:
            start_time = time.time()
            retrieved = job_store.get_job(job.id)
            retrieve_time = time.time() - start_time
            retrieve_times.append(retrieve_time)
            
            assert retrieved is not None
        
        # Análise de performance
        avg_save_time = mean(save_times)
        avg_retrieve_time = mean(retrieve_times)
        
        # Salvamento deve ser rápido (< 5ms)
        assert avg_save_time < 0.005, f"Job save too slow: {avg_save_time:.4f}s"
        
        # Recuperação deve ser muito rápida (< 2ms)
        assert avg_retrieve_time < 0.002, f"Job retrieve too slow: {avg_retrieve_time:.4f}s"
        
        print(f"Job store performance: save={avg_save_time:.4f}s, retrieve={avg_retrieve_time:.4f}s")


class TestLoadTesting:
    """Testes de carga simulados"""
    
    @pytest.mark.load
    async def test_concurrent_validation(self):
        """Testa validação concorrente de arquivos"""
        middleware = ValidationMiddleware()
        
        async def validate_file_concurrent(file_id):
            """Simula validação de arquivo"""
            from unittest.mock import Mock, AsyncMock
            from fastapi import UploadFile
            
            # Cria mock de arquivo
            mock_file = Mock(spec=UploadFile)
            mock_file.filename = f"test_{file_id}.mp3"
            mock_file.read = AsyncMock(return_value=b'\xff\xfb\x90\x00' + b'\x00' * 1000)
            mock_file.seek = AsyncMock()
            
            start_time = time.time()
            
            try:
                file_result, security_result = await middleware.validate_upload(
                    mock_file, 
                    client_ip=f"192.168.1.{file_id % 255}"
                )
                validation_time = time.time() - start_time
                return file_id, validation_time, file_result.valid, security_result.safe
            except Exception as e:
                validation_time = time.time() - start_time
                return file_id, validation_time, False, False
        
        # Executa validações concorrentes
        num_files = 50
        tasks = [validate_file_concurrent(i) for i in range(num_files)]
        results = await asyncio.gather(*tasks)
        
        # Analisa resultados
        validation_times = [result[1] for result in results]
        successful_validations = sum(1 for result in results if result[2] and result[3])
        
        # Verificações de carga
        avg_validation_time = mean(validation_times)
        max_validation_time = max(validation_times)
        
        # Performance deve ser aceitável mesmo sob carga
        assert avg_validation_time < 0.1, f"Validation too slow under load: {avg_validation_time:.4f}s"
        assert max_validation_time < 0.5, f"Worst case too slow: {max_validation_time:.4f}s"
        
        # A maioria das validações deve ser bem-sucedida
        success_rate = successful_validations / num_files
        assert success_rate > 0.8, f"Too many validation failures: {success_rate:.2%}"
        
        print(f"Validation under load: avg={avg_validation_time:.4f}s, max={max_validation_time:.4f}s, success={success_rate:.2%}")
    
    @pytest.mark.load
    def test_memory_usage_under_load(self, job_store):
        """Testa uso de memória sob carga"""
        import psutil
        import gc
        
        # Medição inicial de memória
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Cria muitos jobs para testar uso de memória
        num_jobs = 1000
        jobs = []
        
        for i in range(num_jobs):
            job = Job.create_new(
                input_file=f"/tmp/memory_test_{i}.mp3",
                remove_noise=True,
                normalize_volume=True,
                convert_to_mono=True
            )
            job_store.save_job(job)
            jobs.append(job)
            
            # Medição periódica
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Não deve crescer descontroladamente
                assert memory_growth < 100, f"Memory growth too high: {memory_growth:.1f}MB after {i} jobs"
        
        # Medição final
        final_memory = process.memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        print(f"Memory usage: initial={initial_memory:.1f}MB, final={final_memory:.1f}MB, growth={total_growth:.1f}MB")
        
        # Cleanup e garbage collection
        jobs.clear()
        gc.collect()
        
        # Verifica se memória é liberada
        after_gc_memory = process.memory_info().rss / 1024 / 1024
        memory_released = final_memory - after_gc_memory
        
        print(f"Memory after GC: {after_gc_memory:.1f}MB, released={memory_released:.1f}MB")


class TestStressScenarios:
    """Cenários de stress para testar resiliência"""
    
    @pytest.mark.stress
    async def test_rapid_rate_limit_requests(self):
        """Testa rate limiter com requests muito rápidas"""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        client_id = "stress_client"
        
        # Faz requests o mais rápido possível
        num_requests = 100
        allowed_count = 0
        denied_count = 0
        
        start_time = time.time()
        
        for _ in range(num_requests):
            allowed = await limiter.is_allowed(client_id)
            if allowed:
                allowed_count += 1
            else:
                denied_count += 1
        
        total_time = time.time() - start_time
        
        # Verifica comportamento correto do rate limiter
        assert allowed_count <= 10, f"Too many requests allowed: {allowed_count}"
        assert denied_count >= 90, f"Not enough requests denied: {denied_count}"
        
        # Deve processar rapidamente mesmo com muitas requests
        requests_per_second = num_requests / total_time
        assert requests_per_second > 1000, f"Rate limiter too slow: {requests_per_second:.0f} req/s"
        
        print(f"Rate limiter stress test: {requests_per_second:.0f} req/s, {allowed_count} allowed, {denied_count} denied")
    
    @pytest.mark.stress
    def test_large_job_ids(self, job_store):
        """Testa comportamento com IDs de job muito grandes"""
        # Cria job com arquivo grande (para ID longo)
        large_content = b"a" * 10000  # Conteúdo repetitivo para ID consistente
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            temp_file.write(large_content)
            temp_file_path = temp_file.name
        
        try:
            job = Job.create_new(
                input_file=temp_file_path,
                remove_noise=True,
                normalize_volume=True,
                convert_to_mono=True,
                apply_highpass_filter=True,
                set_sample_rate_16k=True
            )
            
            # ID deve ser consistente e não muito longo
            assert len(job.id) < 100, f"Job ID too long: {len(job.id)} chars"
            
            # Deve ser possível salvar e recuperar
            job_store.save_job(job)
            retrieved = job_store.get_job(job.id)
            
            assert retrieved is not None
            assert retrieved.id == job.id
            
        finally:
            # Cleanup
            Path(temp_file_path).unlink(missing_ok=True)
    
    @pytest.mark.stress
    async def test_simultaneous_cleanup(self, job_store):
        """Testa cleanup simultâneo de jobs"""
        # Cria jobs que vão expirar
        from datetime import datetime, timedelta
        
        expired_jobs = []
        for i in range(10):
            job = Job(
                id=f"cleanup_test_{i}",
                input_file=f"/tmp/cleanup_{i}.mp3",
                status=JobStatus.COMPLETED,
                isolate_vocals=False,
                remove_noise=True,
                normalize_volume=True,
                convert_to_mono=True,
                apply_highpass_filter=True,
                set_sample_rate_16k=True,
                created_at=datetime.now() - timedelta(hours=25),
                expires_at=datetime.now() - timedelta(hours=1)
            )
            job_store.save_job(job)
            expired_jobs.append(job)
        
        # Executa cleanup múltiplas vezes simultaneamente
        cleanup_tasks = [job_store.cleanup_expired() for _ in range(5)]
        results = await asyncio.gather(*cleanup_tasks)
        
        # Verifica que cleanup foi executado sem erros
        total_removed = sum(results)
        assert total_removed >= len(expired_jobs)
        
        # Jobs devem ter sido removidos
        for job in expired_jobs:
            retrieved = job_store.get_job(job.id)
            assert retrieved is None


# Configuração de marcadores para pytest
pytestmark = [
    pytest.mark.asyncio,  # Todos os testes assíncronos
]