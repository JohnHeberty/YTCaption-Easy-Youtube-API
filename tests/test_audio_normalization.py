"""
Testes para Audio Normalization Service - Validação completa com arquivos reais
"""
import pytest
import os
import time
from pathlib import Path
from conftest import AUDIO_PROCESSING_PARAMS, AUDIO_PROCESSING_IDS, BASE_URL

class TestAudioNormalizationService:
    """Suite de testes para validação completa do serviço"""
    
    def test_service_health(self, service_health_check):
        """Testa se o serviço está funcionando"""
        assert service_health_check is True
        
    def test_basic_job_no_processing(self, job_manager, test_audio_file, output_dir):
        """Testa job básico sem processamento (baseline)"""
        # Cria job sem nenhum processamento
        job_data = job_manager.create_job(test_audio_file)
        
        # Valida resposta inicial
        assert 'id' in job_data
        assert job_data['status'] in ['queued', 'processing', 'completed']
        assert 'test_audio_' in job_data['filename']  # Nome agora é único
        
        # Aguarda conclusão
        completed_job = job_manager.wait_for_completion(job_data['id'])
        
        # Valida job concluído
        assert completed_job['status'] == 'completed'
        assert completed_job['progress'] == 100.0
        assert completed_job['error_message'] is None
        assert completed_job['output_file'] is not None
        
        # Baixa e valida resultado
        result_file = job_manager.download_result(
            job_data['id'], 
            f"baseline_{job_data['id']}.webm"
        )
        
        assert result_file.exists()
        assert result_file.stat().st_size > 0
        print(f"✅ Baseline result saved: {result_file}")
        
    @pytest.mark.parametrize("params,feature_name", zip(AUDIO_PROCESSING_PARAMS, AUDIO_PROCESSING_IDS))
    def test_audio_processing_features(self, job_manager, test_audio_file, output_dir, params, feature_name):
        """Testa cada feature de processamento individualmente"""
        
        # Cria job com parâmetros específicos
        job_data = job_manager.create_job(test_audio_file, **params)
        
        # Valida resposta inicial
        assert 'id' in job_data
        assert job_data['status'] in ['queued', 'processing', 'completed']
        
        # Aguarda conclusão com timeout personalizado
        completed_job = job_manager.wait_for_completion(job_data['id'])
        
        # Valida job concluído
        assert completed_job['status'] == 'completed', \
            f"Job failed for {feature_name}: {completed_job.get('error_message', 'Unknown error')}"
        assert completed_job['progress'] == 100.0
        assert completed_job['error_message'] is None
        assert completed_job['output_file'] is not None
        
        # Verifica se parâmetros foram aplicados corretamente
        for param, value in params.items():
            assert completed_job[param] == value, \
                f"Parameter {param} not applied correctly"
        
        # Baixa e valida resultado
        result_file = job_manager.download_result(
            job_data['id'], 
            f"{feature_name}_{job_data['id']}.webm"
        )
        
        assert result_file.exists()
        assert result_file.stat().st_size > 0
        print(f"✅ {feature_name} result saved: {result_file}")
        
    def test_resilience_api_never_crashes(self, job_manager, test_audio_file, api_client):
        """Testa que a API nunca quebra mesmo com jobs problemáticos"""
        
        # Cria múltiplos jobs simultâneos com diferentes parâmetros
        jobs = []
        for i, params in enumerate(AUDIO_PROCESSING_PARAMS[:3]):  # Testa 3 primeiros
            try:
                job_data = job_manager.create_job(test_audio_file, **params)
                jobs.append((job_data['id'], AUDIO_PROCESSING_IDS[i]))
            except Exception as e:
                pytest.fail(f"Failed to create job for {AUDIO_PROCESSING_IDS[i]}: {e}")
        
        # Verifica que a API continua respondendo
        for _ in range(10):  # 10 verificações
            response = api_client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            health_data = response.json()
            assert health_data['status'] == 'healthy'
            time.sleep(1)
            
        # Verifica status de todos os jobs
        for job_id, feature_name in jobs:
            response = api_client.get(f"{BASE_URL}/jobs/{job_id}")
            assert response.status_code == 200, \
                f"API crashed when checking job {job_id} ({feature_name})"
            
            job_data = response.json()
            assert 'status' in job_data
            assert 'progress' in job_data
            print(f"✅ Job {job_id} ({feature_name}): {job_data['status']} - {job_data['progress']}%")
            
    def test_file_validation_and_metadata(self, job_manager, test_audio_file, output_dir):
        """Testa validação de arquivos e metadados"""
        
        # Cria job com processamento completo
        params = {
            'apply_highpass_filter': True,
            'remove_noise': True,
            'convert_to_mono': True,
            'set_sample_rate_16k': True
        }
        
        job_data = job_manager.create_job(test_audio_file, **params)
        completed_job = job_manager.wait_for_completion(job_data['id'])
        
        # Valida metadados
        assert completed_job['file_size_input'] > 0
        assert completed_job['file_size_output'] > 0
        assert completed_job['created_at'] is not None
        assert completed_job['completed_at'] is not None
        
        # Baixa resultado
        result_file = job_manager.download_result(
            job_data['id'], 
            f"full_processing_{job_data['id']}.webm"
        )
        
        # Valida arquivo resultado
        assert result_file.exists()
        file_size = result_file.stat().st_size
        assert file_size > 0
        assert file_size == completed_job['file_size_output']
        
        print(f"✅ Full processing result: {result_file} ({file_size} bytes)")
        
    def test_concurrent_jobs_stability(self, job_manager, test_audio_file, output_dir):
        """Testa estabilidade com múltiplos jobs concorrentes"""
        
        # Cria 3 jobs diferentes simultaneamente
        concurrent_jobs = []
        test_cases = [
            ({'apply_highpass_filter': True}, 'concurrent_highpass'),
            ({'remove_noise': True}, 'concurrent_noise'),
            ({'isolate_vocals': True}, 'concurrent_vocals')
        ]
        
        # Submete todos os jobs
        for params, name in test_cases:
            job_data = job_manager.create_job(test_audio_file, **params)
            concurrent_jobs.append((job_data['id'], name, params))
            print(f"📤 Submitted {name}: {job_data['id']}")
            
        # Aguarda conclusão de todos
        results = []
        for job_id, name, params in concurrent_jobs:
            try:
                completed_job = job_manager.wait_for_completion(job_id)
                result_file = job_manager.download_result(job_id, f"{name}_{job_id}.webm")
                
                results.append({
                    'job_id': job_id,
                    'name': name,
                    'status': completed_job['status'],
                    'file_size': result_file.stat().st_size,
                    'file_path': result_file
                })
                print(f"✅ {name} completed: {result_file}")
                
            except Exception as e:
                pytest.fail(f"Concurrent job {name} failed: {e}")
                
        # Valida que todos completaram com sucesso
        assert len(results) == 3
        for result in results:
            assert result['status'] == 'completed'
            assert result['file_size'] > 0
            
    def test_error_handling_and_recovery(self, job_manager, api_client):
        """Testa handling de erros e recuperação"""
        
        # Testa job com arquivo inválido (simulação)
        try:
            # Tenta acessar job inexistente
            response = api_client.get(f"{BASE_URL}/jobs/invalid-job-id-that-does-not-exist")
            # A API pode retornar 200 com status de erro ou 404, ambos são válidos
            assert response.status_code in [200, 404]
            
            # Verifica que API continua funcionando
            health_response = api_client.get(f"{BASE_URL}/health")
            assert health_response.status_code == 200
            assert health_response.json()['status'] == 'healthy'
            
            print("✅ Error handling working correctly")
            
        except Exception as e:
            pytest.fail(f"Error handling test failed: {e}")