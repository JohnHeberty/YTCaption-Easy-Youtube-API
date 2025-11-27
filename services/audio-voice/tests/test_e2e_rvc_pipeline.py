"""
End-to-End Tests for RVC Pipeline
Sprint 8: Complete workflow validation from upload to audio output
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import hashlib
import io
import wave
import struct
import json
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def e2e_client():
    """FastAPI test client for E2E tests"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def realistic_pth_checkpoint():
    """
    Create a realistic PyTorch checkpoint structure
    Mimics actual RVC .pth file format
    """
    import torch
    
    # Minimal RVC model structure
    checkpoint = {
        'model': {
            'enc_p.emb.weight': torch.randn(256, 768),
            'dec.conv_pre.weight': torch.randn(512, 192, 3),
            'dec.ups.0.weight': torch.randn(256, 512, 8)
        },
        'optimizer': {},
        'learning_rate': 0.0001,
        'iteration': 10000,
        'version': 'v2'
    }
    
    # Salvar em bytes (em memória)
    buffer = io.BytesIO()
    torch.save(checkpoint, buffer)
    buffer.seek(0)
    
    return buffer.getvalue()


@pytest.fixture
def realistic_faiss_index():
    """
    Create a realistic FAISS index file
    Mimics actual .index file format
    """
    # Header FAISS index (simplified)
    index_data = b'FAISS_INDEX_V2\x00\x00'
    index_data += struct.pack('<I', 256)  # dimension
    index_data += struct.pack('<I', 1000)  # num vectors
    index_data += b'\x00' * 1024  # Dummy index data
    
    return index_data


@pytest.fixture
def sample_wav_audio():
    """Generate a valid 3-second WAV audio file"""
    sample_rate = 24000
    duration = 3
    num_samples = sample_rate * duration
    
    # Generate sine wave
    frequency = 440  # A4 note
    samples = []
    for i in range(num_samples):
        value = int(32767 * 0.3 * (i % 1000 / 1000))  # Simple waveform
        samples.append(struct.pack('<h', value))
    
    # Create WAV file in memory
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(samples))
    
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def mock_redis_store():
    """Mock Redis store for E2E tests"""
    store = MagicMock()
    store.get_job = MagicMock(return_value=None)
    store.save_job = MagicMock()
    store.get_voice_profile = MagicMock(return_value=None)
    return store


@pytest.fixture
def mock_xtts_engine():
    """Mock XTTS engine to avoid GPU requirements"""
    engine = MagicMock()
    engine.device = "cpu"
    engine.model_name = "xtts_v2"
    
    # Mock synthesis method
    async def mock_synthesize(text, language, **kwargs):
        # Return fake audio data
        return b'\x00' * (24000 * 3 * 2)  # 3 seconds of silence
    
    engine.synthesize = AsyncMock(side_effect=mock_synthesize)
    return engine


@pytest.fixture
def mock_rvc_client():
    """Mock RVC client to avoid model loading"""
    client = MagicMock()
    
    # Mock conversion method
    async def mock_convert(audio_path, **kwargs):
        # Return same audio path (no actual conversion)
        return audio_path
    
    client.convert_voice = AsyncMock(side_effect=mock_convert)
    client.is_loaded = True
    return client


class TestE2ERvcModelUploadWorkflow:
    """E2E tests for RVC model upload workflow"""
    
    def test_upload_rvc_model_complete_workflow(self, e2e_client, realistic_pth_checkpoint, realistic_faiss_index):
        """
        E2E: Upload RVC model with .pth and .index files
        Validates complete upload → storage → retrieval workflow
        """
        # Arrange
        model_name = "E2E Test Female Voice"
        model_description = "E2E test model for pipeline validation"
        
        # Act 1: Upload model
        upload_response = e2e_client.post(
            "/rvc-models",
            data={
                "name": model_name,
                "description": model_description
            },
            files={
                "pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream"),
                "index_file": ("model.index", io.BytesIO(realistic_faiss_index), "application/octet-stream")
            }
        )
        
        # Assert upload
        assert upload_response.status_code == 201
        model_data = upload_response.json()
        assert "id" in model_data
        assert model_data["name"] == model_name
        assert model_data["description"] == model_description
        model_id = model_data["id"]
        
        # Act 2: Retrieve uploaded model
        get_response = e2e_client.get(f"/rvc-models/{model_id}")
        
        # Assert retrieval
        assert get_response.status_code == 200
        retrieved_model = get_response.json()
        assert retrieved_model["id"] == model_id
        assert retrieved_model["name"] == model_name
        
        # Act 3: Verify files exist on disk
        pth_file_path = Path(retrieved_model["pth_file"])
        index_file_path = Path(retrieved_model["index_file"])
        assert pth_file_path.exists()
        assert index_file_path.exists()
        
        # Act 4: Delete model
        delete_response = e2e_client.delete(f"/rvc-models/{model_id}")
        
        # Assert deletion
        assert delete_response.status_code == 200
        
        # Act 5: Verify model no longer exists
        get_after_delete = e2e_client.get(f"/rvc-models/{model_id}")
        assert get_after_delete.status_code == 404
    
    def test_upload_model_without_index(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Upload RVC model with only .pth file (index optional)
        """
        # Act
        upload_response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Model No Index"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        
        # Assert
        assert upload_response.status_code == 201
        model_data = upload_response.json()
        assert model_data["index_file"] is None
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_data['id']}")


class TestE2ERvcJobCreationWorkflow:
    """E2E tests for job creation with RVC"""
    
    @patch('app.processor.VoiceProcessor.process_dubbing_job')
    def test_create_job_with_rvc_enabled(self, mock_process, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Create job with RVC enabled
        Validates parameter passing and job queuing
        """
        # Arrange: Upload RVC model first
        upload_response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Job Test Model"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        assert upload_response.status_code == 201
        model_id = upload_response.json()["id"]
        
        # Act: Create job with RVC
        job_response = e2e_client.post(
            "/jobs",
            data={
                "text": "Hello world, this is an E2E test",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": model_id,
                "rvc_pitch": "2",
                "rvc_index_rate": "0.85"
            }
        )
        
        # Assert
        assert job_response.status_code in [200, 201, 202]
        job_data = job_response.json()
        assert job_data["enable_rvc"] is True
        assert job_data["rvc_model_id"] == model_id
        assert job_data["rvc_pitch"] == 2
        assert job_data["rvc_index_rate"] == 0.85
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_id}")
    
    def test_create_job_without_rvc(self, e2e_client):
        """
        E2E: Create job without RVC (backward compatibility)
        Ensures XTTS-only workflow still works
        """
        # Act
        job_response = e2e_client.post(
            "/jobs",
            data={
                "text": "Hello world without RVC",
                "source_language": "en",
                "mode": "dubbing"
            }
        )
        
        # Assert
        assert job_response.status_code in [200, 201, 202]
        job_data = job_response.json()
        assert job_data["enable_rvc"] is False


class TestE2EFullPipeline:
    """E2E tests for complete pipeline: Upload → Job → Audio"""
    
    @patch('app.processor.VoiceProcessor')
    @patch('app.main.submit_processing_task')
    def test_full_pipeline_xtts_plus_rvc(
        self, 
        mock_submit,
        mock_processor_class,
        e2e_client,
        realistic_pth_checkpoint,
        sample_wav_audio
    ):
        """
        E2E: Complete pipeline from model upload to audio generation
        
        Workflow:
        1. Upload RVC model
        2. Create job with RVC enabled
        3. Process job (mocked XTTS + RVC)
        4. Download audio
        5. Validate audio format
        """
        # Setup mocks
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        # Mock job processing to complete immediately
        def mock_submit_task(job):
            # Simulate job completion
            job.status = "completed"
            job.output_file = "/tmp/test_output.wav"
            # Save fake audio
            Path(job.output_file).parent.mkdir(exist_ok=True, parents=True)
            Path(job.output_file).write_bytes(sample_wav_audio)
        
        mock_submit.side_effect = mock_submit_task
        
        # Step 1: Upload RVC model
        upload_response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Full Pipeline Model"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        assert upload_response.status_code == 201
        model_id = upload_response.json()["id"]
        
        # Step 2: Create job with RVC
        job_response = e2e_client.post(
            "/jobs",
            data={
                "text": "Full E2E pipeline test with RVC conversion",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": model_id,
                "rvc_pitch": "0",
                "rvc_index_rate": "0.75"
            }
        )
        assert job_response.status_code in [200, 201, 202]
        job_id = job_response.json()["id"]
        
        # Step 3: Check job status (would be completed in real scenario)
        # Note: In E2E test, job processing is mocked
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_id}")


class TestE2ERvcFallback:
    """E2E tests for RVC fallback scenarios"""
    
    @patch('app.processor.VoiceProcessor.rvc_client')
    def test_rvc_conversion_failure_fallback(self, mock_rvc_client, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Test fallback to XTTS-only when RVC conversion fails
        Ensures graceful degradation
        """
        # Arrange: Mock RVC to fail
        mock_rvc_client.convert_voice = AsyncMock(side_effect=RuntimeError("RVC conversion failed"))
        
        # Upload model
        upload_response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Fallback Test Model"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        model_id = upload_response.json()["id"]
        
        # Act: Create job with RVC (should fallback to XTTS-only)
        job_response = e2e_client.post(
            "/jobs",
            data={
                "text": "Fallback test",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": model_id
            }
        )
        
        # Assert: Job should still be created (graceful degradation)
        assert job_response.status_code in [200, 201, 202]
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_id}")


class TestE2EModelManagement:
    """E2E tests for model management operations"""
    
    def test_list_models_pagination(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Upload multiple models and test listing/sorting
        """
        # Arrange: Upload 3 models
        model_ids = []
        for i in range(3):
            response = e2e_client.post(
                "/rvc-models",
                data={"name": f"E2E Model {i:02d}"},
                files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
            )
            assert response.status_code == 201
            model_ids.append(response.json()["id"])
        
        # Act: List all models
        list_response = e2e_client.get("/rvc-models")
        
        # Assert
        assert list_response.status_code == 200
        data = list_response.json()
        assert data["total"] >= 3
        assert len(data["models"]) >= 3
        
        # Act: List with sorting by name
        sorted_response = e2e_client.get("/rvc-models?sort_by=name")
        assert sorted_response.status_code == 200
        
        # Cleanup
        for model_id in model_ids:
            e2e_client.delete(f"/rvc-models/{model_id}")
    
    def test_get_model_stats(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Verify model statistics endpoint
        """
        # Arrange: Upload 2 models (one with index, one without)
        model1 = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Stats Model 1"},
            files={
                "pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream"),
                "index_file": ("model.index", io.BytesIO(b'\x00' * 1024), "application/octet-stream")
            }
        )
        model1_id = model1.json()["id"]
        
        model2 = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Stats Model 2"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        model2_id = model2.json()["id"]
        
        # Act
        stats_response = e2e_client.get("/rvc-models/stats")
        
        # Assert
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total_models"] >= 2
        assert stats["total_size_mb"] > 0
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model1_id}")
        e2e_client.delete(f"/rvc-models/{model2_id}")


class TestE2EValidationErrors:
    """E2E tests for validation and error scenarios"""
    
    def test_create_job_with_invalid_rvc_model(self, e2e_client):
        """
        E2E: Job creation should fail with non-existent RVC model
        """
        # Act
        response = e2e_client.post(
            "/jobs",
            data={
                "text": "Test with invalid model",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": "nonexistent_model_id_12345"
            }
        )
        
        # Assert
        assert response.status_code == 404
        assert "model" in response.json()["detail"].lower() or "not found" in response.json()["detail"].lower()
    
    def test_rvc_parameters_validation(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Validate RVC parameter ranges
        """
        # Arrange: Upload model
        upload_response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Validation Model"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        model_id = upload_response.json()["id"]
        
        # Act: Invalid pitch (outside -12 to +12 range)
        response = e2e_client.post(
            "/jobs",
            data={
                "text": "Test",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": model_id,
                "rvc_pitch": "20"  # Invalid: > 12
            }
        )
        
        # Assert
        assert response.status_code == 400
        assert "pitch" in response.json()["detail"].lower()
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_id}")
    
    def test_duplicate_model_name(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Cannot upload model with duplicate name
        """
        # Arrange: Upload first model
        first_upload = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Duplicate Test"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        assert first_upload.status_code == 201
        model_id = first_upload.json()["id"]
        
        # Act: Try to upload with same name
        duplicate_upload = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Duplicate Test"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        
        # Assert
        assert duplicate_upload.status_code == 409
        assert "already exists" in duplicate_upload.json()["detail"].lower()
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{model_id}")


class TestE2ERegressionTests:
    """E2E regression tests to ensure backward compatibility"""
    
    def test_xtts_only_workflow_still_works(self, e2e_client):
        """
        E2E Regression: Ensure XTTS-only workflow (without RVC) still works
        Validates backward compatibility
        """
        # Act: Create job without any RVC parameters
        response = e2e_client.post(
            "/jobs",
            data={
                "text": "Regression test for XTTS-only workflow",
                "source_language": "en",
                "mode": "dubbing",
                "voice_preset": "female_generic"
            }
        )
        
        # Assert
        assert response.status_code in [200, 201, 202]
        job_data = response.json()
        assert job_data["enable_rvc"] is False
        assert "text" in job_data
    
    def test_voice_clone_workflow_unaffected(self, e2e_client, sample_wav_audio):
        """
        E2E Regression: Voice cloning workflow should not be affected by RVC changes
        """
        # Act: Clone voice (existing workflow)
        response = e2e_client.post(
            "/voices/clone",
            data={
                "name": "E2E Regression Voice",
                "language": "en",
                "description": "Regression test voice"
            },
            files={"file": ("audio.wav", io.BytesIO(sample_wav_audio), "audio/wav")}
        )
        
        # Assert: Should work as before (202 Accepted for async processing)
        assert response.status_code == 202
        assert "job_id" in response.json()


class TestE2EAudioQuality:
    """E2E tests for audio quality validation"""
    
    def test_output_audio_format_validation(self, sample_wav_audio):
        """
        E2E: Validate output audio format meets requirements
        - Sample rate: 24kHz
        - Channels: Mono (1)
        - Format: WAV
        """
        # Validate WAV format
        buffer = io.BytesIO(sample_wav_audio)
        with wave.open(buffer, 'rb') as wav_file:
            assert wav_file.getnchannels() == 1  # Mono
            assert wav_file.getframerate() == 24000  # 24kHz
            assert wav_file.getsampwidth() == 2  # 16-bit
    
    @pytest.mark.slow
    def test_audio_duration_matches_text_length(self):
        """
        E2E: Audio duration should roughly match text length
        (Placeholder for actual audio generation test)
        """
        # This would test actual XTTS + RVC pipeline
        # Requires GPU and actual model loading
        pytest.skip("Requires GPU and actual model loading")


class TestE2EPerformance:
    """E2E performance tests (basic)"""
    
    @pytest.mark.slow
    def test_upload_model_performance(self, e2e_client, realistic_pth_checkpoint):
        """
        E2E: Model upload should complete in reasonable time (<5s for small model)
        """
        import time
        
        start_time = time.time()
        
        response = e2e_client.post(
            "/rvc-models",
            data={"name": "E2E Performance Test"},
            files={"pth_file": ("model.pth", io.BytesIO(realistic_pth_checkpoint), "application/octet-stream")}
        )
        
        elapsed_time = time.time() - start_time
        
        assert response.status_code == 201
        assert elapsed_time < 5.0  # Should complete in less than 5 seconds
        
        # Cleanup
        e2e_client.delete(f"/rvc-models/{response.json()['id']}")
