"""
Testes de chaos engineering para validar resiliência
"""
import pytest
import asyncio
import random
import threading
import time
from unittest.mock import patch, Mock, AsyncMock
from pathlib import Path
import tempfile

from app.models import Job, JobStatus
from app.exceptions import CircuitBreaker, SecurityError, ResourceError


class TestChaosEngineering:
    """Testes de chaos engineering para validar resiliência do sistema"""
    
    @pytest.mark.chaos
    async def test_redis_connection_failures(self, job_store):
        """Simula falhas de conexão Redis durante operações"""
        
        async def intermittent_redis_failure():
            """Simula falhas intermitentes no Redis"""
            original_execute = job_store.redis.execute_command
            
            call_count = 0
            def failing_execute(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                # Falha aleatoriamente em ~30% das chamadas
                if random.random() < 0.3:
                    raise ConnectionError("Redis connection lost")
                
                return original_execute(*args, **kwargs)
            
            # Aplica o patch
            with patch.object(job_store.redis, 'execute_command', side_effect=failing_execute):
                # Tenta operações durante as falhas
                jobs_created = 0
                jobs_retrieved = 0
                errors = 0
                
                for i in range(20):
                    try:
                        # Cria job
                        job = Job.create_new(
                            input_file=f"/tmp/chaos_{i}.mp3",
                            remove_noise=True
                        )
                        
                        # Tenta salvar (pode falhar)
                        job_store.save_job(job)
                        jobs_created += 1
                        
                        # Tenta recuperar (pode falhar)
                        retrieved = job_store.get_job(job.id)
                        if retrieved:
                            jobs_retrieved += 1
                            
                    except Exception as e:
                        errors += 1
                        # Falhas são esperadas, mas não devem quebrar tudo
                        assert isinstance(e, (ConnectionError, TimeoutError))
                
                return jobs_created, jobs_retrieved, errors, call_count
        
        # Executa teste com falhas
        created, retrieved, errors, calls = await intermittent_redis_failure()
        
        # Verifica resiliência
        assert errors > 0, "Expected some Redis failures"
        assert created > 0, "System should handle some operations despite failures"
        
        print(f"Redis chaos test: {created} jobs created, {retrieved} retrieved, {errors} errors out of {calls} calls")
    
    @pytest.mark.chaos
    async def test_resource_exhaustion_simulation(self):
        """Simula esgotamento de recursos (memória, CPU, disco)"""
        from app.resource_manager import ResourceMonitor
        
        # Mock do psutil para simular recursos baixos
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Simula sistema com poucos recursos
            mock_memory.return_value = Mock(percent=95)  # 95% de uso de memória
            mock_cpu.return_value = 98  # 98% de uso de CPU
            mock_disk.return_value = Mock(percent=90)  # 90% de uso de disco
            
            monitor = ResourceMonitor()
            
            # Sistema deve detectar recursos baixos
            health = await monitor.check_system_health()
            assert not health.healthy, "System should detect resource exhaustion"
            assert "memory" in health.warnings or "cpu" in health.warnings or "disk" in health.warnings
            
            # Tenta operação que requer recursos
            with pytest.raises(ResourceError):
                await monitor.acquire_processing_slot()
            
            print(f"Resource exhaustion detected: {health.warnings}")
    
    @pytest.mark.chaos
    async def test_concurrent_circuit_breaker_trips(self):
        """Testa circuit breaker com falhas concorrentes"""
        
        # Cria circuit breaker com limite baixo para forçar trip
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=1,
            expected_exception=Exception
        )
        
        # Função que falha propositalmente
        @circuit_breaker
        async def failing_operation(operation_id):
            if random.random() < 0.8:  # 80% de chance de falha
                raise Exception(f"Simulated failure in operation {operation_id}")
            return f"Success {operation_id}"
        
        # Executa operações concorrentes
        num_operations = 50
        tasks = [failing_operation(i) for i in range(num_operations)]
        
        # Aguarda todas as operações (algumas vão falhar)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analisa resultados
        successes = [r for r in results if isinstance(r, str)]
        failures = [r for r in results if isinstance(r, Exception)]
        circuit_open_errors = [r for r in failures if "Circuit breaker is OPEN" in str(r)]
        
        # Verifica comportamento do circuit breaker
        assert len(circuit_open_errors) > 0, "Circuit breaker should have tripped"
        assert len(successes) < num_operations * 0.3, "Too many successes during chaos"
        
        print(f"Circuit breaker chaos: {len(successes)} successes, {len(failures)} failures, {len(circuit_open_errors)} circuit open")
        
        # Aguarda reset do circuit breaker
        await asyncio.sleep(1.5)
        
        # Testa se circuit breaker se recupera
        recovery_result = await failing_operation(999)
        if not isinstance(recovery_result, Exception):
            print("Circuit breaker recovered successfully")
    
    @pytest.mark.chaos
    def test_file_system_chaos(self):
        """Simula problemas no sistema de arquivos"""
        from app.resource_manager import TempFileManager
        
        # Testa comportamento com diretório temporário inacessível
        with patch('tempfile.mkdtemp') as mock_mkdtemp, \
             patch('pathlib.Path.mkdir') as mock_mkdir:
            
            # Simula falha na criação de diretório temporário
            mock_mkdtemp.side_effect = OSError("No space left on device")
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            manager = TempFileManager()
            
            # Deve lidar graciosamente com falhas do sistema de arquivos
            with pytest.raises((OSError, PermissionError)):
                with manager.temp_directory() as temp_dir:
                    pass
            
            print("File system chaos handled gracefully")
    
    @pytest.mark.chaos
    async def test_random_validation_failures(self):
        """Simula falhas aleatórias na validação de arquivos"""
        from app.security_validator import FileValidator, SecurityChecker
        
        validator = FileValidator()
        security_checker = SecurityChecker()
        
        # Mock que falha aleatoriamente
        original_validate = validator.validate_file_format
        original_check = security_checker.check_file_security
        
        def chaotic_validate(*args, **kwargs):
            if random.random() < 0.3:  # 30% chance de falha
                raise SecurityError("Chaotic validation failure", error_code="CHAOS_VALIDATION")
            return original_validate(*args, **kwargs)
        
        async def chaotic_security_check(*args, **kwargs):
            if random.random() < 0.2:  # 20% chance de falha
                raise SecurityError("Chaotic security failure", error_code="CHAOS_SECURITY")
            return await original_check(*args, **kwargs)
        
        # Aplica patches caóticos
        with patch.object(validator, 'validate_file_format', side_effect=chaotic_validate), \
             patch.object(security_checker, 'check_file_security', side_effect=chaotic_security_check):
            
            successful_validations = 0
            failed_validations = 0
            
            # Tenta validar múltiplos arquivos
            for i in range(20):
                try:
                    # Cria arquivo temporário simulado
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        temp_file.write(b'\xff\xfb\x90\x00' + b'\x00' * 1000)
                        temp_path = Path(temp_file.name)
                    
                    try:
                        # Tenta validação
                        file_result = validator.validate_file_format(temp_path)
                        security_result = await security_checker.check_file_security(temp_path)
                        
                        if file_result.valid and security_result.safe:
                            successful_validations += 1
                        else:
                            failed_validations += 1
                            
                    finally:
                        temp_path.unlink(missing_ok=True)
                        
                except SecurityError as e:
                    failed_validations += 1
                    assert "CHAOS" in e.error_code
            
            # Sistema deve continuar funcionando apesar das falhas caóticas
            assert successful_validations > 0, "Some validations should succeed despite chaos"
            assert failed_validations > 0, "Expected some chaotic failures"
            
            print(f"Validation chaos: {successful_validations} successful, {failed_validations} failed")


class TestFailureRecovery:
    """Testes de recuperação de falhas"""
    
    @pytest.mark.recovery
    async def test_job_recovery_after_crash(self, job_store):
        """Testa recuperação de jobs após crash simulado"""
        
        # Cria jobs em diferentes estados
        jobs = []
        
        # Job pendente
        pending_job = Job.create_new(
            input_file="/tmp/pending.mp3",
            remove_noise=True
        )
        pending_job.status = JobStatus.PENDING
        jobs.append(pending_job)
        
        # Job em processamento
        processing_job = Job.create_new(
            input_file="/tmp/processing.mp3",
            normalize_volume=True
        )
        processing_job.status = JobStatus.PROCESSING
        jobs.append(processing_job)
        
        # Job completado
        completed_job = Job.create_new(
            input_file="/tmp/completed.mp3",
            convert_to_mono=True
        )
        completed_job.status = JobStatus.COMPLETED
        completed_job.output_file = "/tmp/completed_output.mp3"
        jobs.append(completed_job)
        
        # Salva todos os jobs
        for job in jobs:
            job_store.save_job(job)
        
        # Simula crash - interrompe jobs em processamento
        crashed_jobs = []
        for job in jobs:
            if job.status == JobStatus.PROCESSING:
                job.status = JobStatus.FAILED
                job.error_message = "System crash during processing"
                crashed_jobs.append(job)
        
        # Simula recuperação do sistema
        recovery_actions = []
        
        for job in jobs:
            retrieved = job_store.get_job(job.id)
            
            if retrieved.status == JobStatus.PENDING:
                # Jobs pendentes podem ser reprocessados
                recovery_actions.append(f"Requeue job {job.id}")
                
            elif retrieved.status == JobStatus.PROCESSING:
                # Jobs em processamento devem ser marcados como falhados
                retrieved.status = JobStatus.FAILED
                retrieved.error_message = "Recovered from crash"
                job_store.save_job(retrieved)
                recovery_actions.append(f"Mark job {job.id} as failed due to crash")
                
            elif retrieved.status == JobStatus.COMPLETED:
                # Jobs completados devem permanecer intactos
                recovery_actions.append(f"Job {job.id} already completed - no action needed")
        
        # Verifica recuperação
        assert len(recovery_actions) == len(jobs)
        
        # Jobs em processamento devem ter sido marcados como falhados
        for job in crashed_jobs:
            recovered = job_store.get_job(job.id)
            assert recovered.status == JobStatus.FAILED
            assert "crash" in recovered.error_message.lower()
        
        print(f"Crash recovery: {len(recovery_actions)} recovery actions taken")
    
    @pytest.mark.recovery
    async def test_partial_failure_recovery(self):
        """Testa recuperação de falhas parciais no processamento"""
        from app.processor_new import AudioProcessor
        
        processor = AudioProcessor()
        
        # Mock que falha em operações específicas
        with patch('app.processor_new.AudioSegment.from_file') as mock_from_file:
            
            # Simula falha na leitura de arquivo corrompido
            mock_from_file.side_effect = Exception("Corrupted audio file")
            
            job = Job.create_new(
                input_file="/tmp/corrupted.mp3",
                remove_noise=True,
                normalize_volume=True
            )
            
            # Processamento deve falhar graciosamente
            result = await processor.process_audio(job)
            
            # Deve retornar resultado com erro
            assert not result.success
            assert "corrupted" in result.error.lower() or "failed" in result.error.lower()
            
            # Job deve estar marcado como falhado
            assert job.status == JobStatus.FAILED
            assert job.error_message is not None
            
            print(f"Partial failure handled: {result.error}")
    
    @pytest.mark.recovery
    async def test_timeout_recovery(self):
        """Testa recuperação de operações que excedem timeout"""
        
        # Simula operação lenta
        async def slow_operation():
            await asyncio.sleep(10)  # Operação muito lenta
            return "Should not reach here"
        
        # Testa timeout com recuperação
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(slow_operation(), timeout=1.0)
            assert False, "Operation should have timed out"
            
        except asyncio.TimeoutError:
            elapsed_time = time.time() - start_time
            
            # Deve ter respeitado o timeout
            assert 0.9 < elapsed_time < 1.5, f"Timeout not respected: {elapsed_time:.2f}s"
            
            # Simula ação de recuperação
            recovery_action = "Operation cancelled due to timeout - resources cleaned up"
            
            print(f"Timeout recovery: {recovery_action}")


class TestEdgeCases:
    """Testes para casos extremos e edge cases"""
    
    @pytest.mark.edge_case
    def test_empty_files(self):
        """Testa comportamento com arquivos vazios"""
        from app.security_validator import FileValidator
        
        validator = FileValidator()
        
        # Cria arquivo vazio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            empty_path = Path(temp_file.name)
        
        try:
            # Validação deve detectar arquivo vazio
            result = validator.validate_file_format(empty_path)
            
            assert not result.valid
            assert "empty" in result.error.lower() or "size" in result.error.lower()
            
        finally:
            empty_path.unlink(missing_ok=True)
    
    @pytest.mark.edge_case
    def test_very_large_files(self):
        """Testa comportamento com arquivos muito grandes"""
        from app.security_validator import SecurityChecker
        
        # Simula arquivo muito grande através de mock
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=500 * 1024 * 1024)  # 500MB
            
            security_checker = SecurityChecker()
            
            # Cria arquivo temporário (pequeno, mas com stat mockado)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(b'\xff\xfb\x90\x00' + b'test' * 1000)
                large_file_path = Path(temp_file.name)
            
            try:
                # Verificação de segurança deve detectar arquivo muito grande
                with pytest.raises(SecurityError) as exc_info:
                    await security_checker.check_file_security(large_file_path)
                
                assert "size" in str(exc_info.value).lower()
                
            finally:
                large_file_path.unlink(missing_ok=True)
    
    @pytest.mark.edge_case
    def test_unicode_filenames(self, job_store):
        """Testa comportamento com nomes de arquivo unicode"""
        
        unicode_names = [
            "测试文件.mp3",  # Chinês
            "archivo_prueba_ñ.mp3",  # Espanhol com ñ
            "файл_тест.mp3",  # Russo
            "🎵_music_file_🎵.mp3",  # Emojis
            "file with spaces & symbols!@#$%.mp3"
        ]
        
        for filename in unicode_names:
            try:
                job = Job.create_new(
                    input_file=f"/tmp/{filename}",
                    remove_noise=True
                )
                
                # Deve conseguir criar e salvar job com nome unicode
                job_store.save_job(job)
                retrieved = job_store.get_job(job.id)
                
                assert retrieved is not None
                assert retrieved.input_file == job.input_file
                
                print(f"Unicode filename handled: {filename}")
                
            except Exception as e:
                # Se falhar, deve ser com erro específico, não crash
                assert isinstance(e, (ValueError, SecurityError))
                print(f"Unicode filename rejected (expected): {filename} - {e}")


# Configurações de timeout para testes de chaos
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.timeout(30)  # Timeout de 30s para testes de chaos
]