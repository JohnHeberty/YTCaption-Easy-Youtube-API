"""
Testes unitários para serialização de Jobs
"""
import pytest
from datetime import datetime, timedelta
from app.models import Job, JobMode, JobStatus


def test_job_serialization_preserves_input_file():
    """Testa se input_file é preservado na serialização"""
    job = Job.create_new(mode=JobMode.CLONE_VOICE, voice_name="test")
    job.input_file = "/app/uploads/test.wav"
    
    # Serializa
    job_dict = job.model_dump()
    
    # Verifica
    assert 'input_file' in job_dict
    assert job_dict['input_file'] == "/app/uploads/test.wav"
    print("✅ test_job_serialization_preserves_input_file passed")


def test_job_serialization_with_exclude_none_false():
    """Testa serialização com exclude_none=False"""
    job = Job.create_new(mode=JobMode.CLONE_VOICE, voice_name="test")
    job.input_file = "/app/uploads/test.wav"
    
    # Serializa com exclude_none=False
    job_dict = job.model_dump(mode='json', exclude_none=False)
    
    # Verifica que todos os campos estão presentes
    assert 'input_file' in job_dict
    assert job_dict['input_file'] == "/app/uploads/test.wav"
    assert 'id' in job_dict
    assert 'mode' in job_dict
    assert 'status' in job_dict
    print("✅ test_job_serialization_with_exclude_none_false passed")


def test_job_deserialization_preserves_input_file():
    """Testa se input_file é preservado na deserialização"""
    job_dict = {
        'id': 'test_123',
        'mode': 'clone_voice',
        'status': 'queued',
        'input_file': '/app/uploads/test.wav',
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(hours=24)).isoformat(),
        'progress': 0.0
    }
    
    # Deserializa
    job = Job(**job_dict)
    
    # Verifica
    assert job.input_file is not None
    assert job.input_file == '/app/uploads/test.wav'
    print("✅ test_job_deserialization_preserves_input_file passed")


def test_job_roundtrip_serialization():
    """Testa serialização completa (roundtrip)"""
    # Cria job
    original = Job.create_new(mode=JobMode.CLONE_VOICE, voice_name="test")
    original.input_file = "/path/to/file.wav"
    original.voice_description = "Test voice"
    original.source_language = "pt-BR"
    
    # Serializa
    job_dict = original.model_dump(mode='json', exclude_none=False)
    
    # Deserializa
    reconstructed = Job(**job_dict)
    
    # Verifica
    assert reconstructed.id == original.id
    assert reconstructed.input_file == original.input_file
    assert reconstructed.mode == original.mode
    assert reconstructed.voice_name == original.voice_name
    assert reconstructed.voice_description == original.voice_description
    assert reconstructed.source_language == original.source_language
    print("✅ test_job_roundtrip_serialization passed")


def test_job_with_none_input_file():
    """Testa job sem input_file (dublagem simples)"""
    job = Job.create_new(
        mode=JobMode.DUBBING,
        text="Test text",
        source_language="pt-BR",
        voice_preset="female_generic"
    )
    
    # input_file deve ser None para dublagem simples
    assert job.input_file is None
    
    # Serializa
    job_dict = job.model_dump(mode='json', exclude_none=False)
    
    # Verifica que input_file está presente (como None)
    assert 'input_file' in job_dict
    assert job_dict['input_file'] is None
    
    # Deserializa
    reconstructed = Job(**job_dict)
    assert reconstructed.input_file is None
    print("✅ test_job_with_none_input_file passed")


def test_job_json_serialization():
    """Testa serialização JSON (model_dump_json)"""
    job = Job.create_new(mode=JobMode.CLONE_VOICE, voice_name="test")
    job.input_file = "/app/uploads/test.wav"
    
    # Serializa para JSON string
    json_str = job.model_dump_json()
    
    # Verifica que é uma string
    assert isinstance(json_str, str)
    assert 'input_file' in json_str
    assert '/app/uploads/test.wav' in json_str
    
    # Deserializa de volta
    reconstructed = Job.model_validate_json(json_str)
    assert reconstructed.input_file == "/app/uploads/test.wav"
    print("✅ test_job_json_serialization passed")


def test_multiple_jobs_serialization():
    """Testa serialização de múltiplos jobs"""
    jobs = [
        Job.create_new(mode=JobMode.CLONE_VOICE, voice_name=f"voice_{i}")
        for i in range(5)
    ]
    
    # Define input_file para todos
    for i, job in enumerate(jobs):
        job.input_file = f"/app/uploads/test_{i}.wav"
    
    # Serializa todos
    job_dicts = [job.model_dump(mode='json', exclude_none=False) for job in jobs]
    
    # Verifica
    for i, job_dict in enumerate(job_dicts):
        assert 'input_file' in job_dict
        assert job_dict['input_file'] == f"/app/uploads/test_{i}.wav"
    
    # Deserializa todos
    reconstructed = [Job(**job_dict) for job_dict in job_dicts]
    
    # Verifica
    for i, job in enumerate(reconstructed):
        assert job.input_file == f"/app/uploads/test_{i}.wav"
    
    print("✅ test_multiple_jobs_serialization passed")


if __name__ == "__main__":
    # Roda todos os testes
    print("\n🧪 Running serialization tests...\n")
    
    test_job_serialization_preserves_input_file()
    test_job_serialization_with_exclude_none_false()
    test_job_deserialization_preserves_input_file()
    test_job_roundtrip_serialization()
    test_job_with_none_input_file()
    test_job_json_serialization()
    test_multiple_jobs_serialization()
    
    print("\n✅ All serialization tests passed!\n")
