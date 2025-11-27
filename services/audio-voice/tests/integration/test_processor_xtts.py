"""
Testes de Integração: VoiceProcessor com XTTS
Sprint 3 - Integração com processor.py
"""
import pytest
import os
import asyncio
from pathlib import Path

from app.processor import VoiceProcessor
from app.models import Job, JobMode, JobStatus, VoiceProfile


@pytest.fixture
def processor_xtts():
    """VoiceProcessor configurado com XTTS"""
    return VoiceProcessor(use_xtts=True)


@pytest.fixture
def processor_fallback():
    """VoiceProcessor configurado com fallback (F5TTS ou OpenVoice)"""
    return VoiceProcessor(use_xtts=False)


@pytest.fixture
def reference_audio():
    """Áudio de referência para clonagem"""
    audio_path = "/app/uploads/clone_20251126031159965237.ogg"
    if not os.path.exists(audio_path):
        pytest.skip(f"Reference audio not found: {audio_path}")
    return audio_path


@pytest.fixture
def temp_output_dir(tmp_path):
    """Diretório temporário para outputs"""
    output_dir = tmp_path / "processed"
    output_dir.mkdir(exist_ok=True)
    return output_dir


class TestProcessorXTTSDubbing:
    """Testes de dubbing via VoiceProcessor com XTTS"""
    
    @pytest.mark.asyncio
    async def test_processor_xtts_dubbing_basic(self, processor_xtts, temp_output_dir, monkeypatch):
        """
        Testa dubbing básico (sem clonagem) via processor com XTTS
        
        Valida:
        - Job inicia como QUEUED
        - Job muda para PROCESSING
        - Job termina como COMPLETED
        - Áudio gerado é válido
        """
        # Mock settings para usar temp_output_dir
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        # Cria job de dubbing
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Olá, mundo! Este é um teste de dublagem.",
            source_language="pt",
            target_language="pt",
            cache_ttl_hours=1
        )
        
        # Estado inicial
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0.0
        
        # Processa job
        result = await processor_xtts.process_dubbing_job(job)
        
        # Valida resultado
        assert result.status == JobStatus.COMPLETED
        assert result.progress == 100.0
        assert result.output_file is not None
        assert os.path.exists(result.output_file)
        assert result.duration > 0
        assert result.file_size_output > 0
        
        # Valida áudio WAV
        with open(result.output_file, 'rb') as f:
            header = f.read(12)
            assert header[:4] == b'RIFF'
            assert header[8:12] == b'WAVE'
    
    @pytest.mark.asyncio
    async def test_processor_xtts_dubbing_with_cloning(
        self, processor_xtts, reference_audio, temp_output_dir, monkeypatch
    ):
        """
        Testa dubbing com clonagem de voz via processor com XTTS
        
        Valida:
        - VoiceProfile usado no dubbing
        - Job completa com sucesso
        - Áudio gerado com voz clonada
        """
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        # Primeiro: Clona voz
        engine = processor_xtts._get_tts_engine()
        voice_profile = await engine.clone_voice(
            audio_path=reference_audio,
            language="pt",
            voice_name="Test Clone Voice"
        )
        
        # Cria job de dubbing com clonagem
        job = Job.create_new(
            mode=JobMode.DUBBING_WITH_CLONE,
            text="Este áudio foi gerado com voz clonada.",
            source_language="pt",
            voice_id=voice_profile.id,
            cache_ttl_hours=1
        )
        
        # Processa job com voice_profile
        result = await processor_xtts.process_dubbing_job(job, voice_profile=voice_profile)
        
        # Valida
        assert result.status == JobStatus.COMPLETED
        assert result.output_file is not None
        assert os.path.exists(result.output_file)
        assert result.duration > 0
    
    @pytest.mark.asyncio
    async def test_processor_xtts_dubbing_empty_text(self, processor_xtts, temp_output_dir, monkeypatch):
        """
        Testa validação de texto vazio
        
        Valida:
        - ValueError lançado para texto vazio
        - Job marcado como FAILED
        """
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="",  # Texto vazio
            source_language="pt",
            cache_ttl_hours=1
        )
        
        # Deve falhar com ValueError
        with pytest.raises(Exception):  # DubbingException wraps ValueError
            await processor_xtts.process_dubbing_job(job)
        
        # Job deve estar FAILED
        assert job.status == JobStatus.FAILED
        assert job.error_message is not None


class TestProcessorXTTSCloning:
    """Testes de clonagem de voz via VoiceProcessor com XTTS"""
    
    @pytest.mark.asyncio
    async def test_processor_xtts_cloning_basic(
        self, processor_xtts, reference_audio, temp_output_dir, monkeypatch
    ):
        """
        Testa clonagem de voz via processor com XTTS
        
        Valida:
        - Job inicia como QUEUED
        - VoiceProfile criado
        - Job termina como COMPLETED
        - voice_id armazenado no job
        """
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        # Cria job de clonagem
        job = Job.create_new(
            mode=JobMode.CLONE_VOICE,
            voice_name="Test Voice Clone",
            source_language="pt",
            voice_description="Voz de teste para XTTS",
            cache_ttl_hours=1
        )
        
        # Define input_file (áudio de referência)
        job.input_file = reference_audio
        
        # Estado inicial
        assert job.status == JobStatus.QUEUED
        assert job.voice_id is None
        
        # Processa job
        voice_profile = await processor_xtts.process_clone_job(job)
        
        # Valida VoiceProfile
        assert isinstance(voice_profile, VoiceProfile)
        assert voice_profile.id is not None
        assert voice_profile.name == "Test Voice Clone"
        assert voice_profile.language == "pt"
        assert voice_profile.reference_audio_path == reference_audio
        
        # Valida Job
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100.0
        assert job.voice_id == voice_profile.id
        assert job.output_file == voice_profile.profile_path
    
    @pytest.mark.asyncio
    async def test_processor_xtts_cloning_invalid_audio(
        self, processor_xtts, temp_output_dir, monkeypatch
    ):
        """
        Testa clonagem com áudio inexistente
        
        Valida:
        - FileNotFoundError lançado
        - Job marcado como FAILED
        """
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        job = Job.create_new(
            mode=JobMode.CLONE_VOICE,
            voice_name="Invalid Voice",
            source_language="pt",
            cache_ttl_hours=1
        )
        
        # Áudio inexistente
        job.input_file = "/tmp/nonexistent_audio.wav"
        
        # Deve falhar
        with pytest.raises(Exception):  # VoiceCloneException wraps FileNotFoundError
            await processor_xtts.process_clone_job(job)
        
        # Job deve estar FAILED
        assert job.status == JobStatus.FAILED
        assert job.error_message is not None


class TestProcessorFallback:
    """Testes de fallback para F5TTS/OpenVoice"""
    
    @pytest.mark.asyncio
    async def test_processor_fallback_to_f5tts(self, processor_fallback, monkeypatch):
        """
        Testa fallback para F5TTS quando use_xtts=False
        
        Valida:
        - Engine retornada é F5TTSClient ou OpenVoiceClient (não XTTS)
        """
        # Mock env var para usar f5tts
        monkeypatch.setenv('TTS_ENGINE', 'f5tts')
        
        # Força recarregar engine
        processor_fallback._engine = None
        
        # Obtém engine
        engine = processor_fallback._get_tts_engine()
        
        # Valida que NÃO é XTTSClient
        from app.xtts_client import XTTSClient
        assert not isinstance(engine, XTTSClient)
        
        # Deve ser F5TTSClient ou OpenVoiceClient
        assert hasattr(engine, 'generate_dubbing')
        assert hasattr(engine, 'clone_voice')


class TestProcessorJobLifecycle:
    """Testes de ciclo de vida completo de jobs"""
    
    @pytest.mark.asyncio
    async def test_processor_complete_workflow(
        self, processor_xtts, reference_audio, temp_output_dir, monkeypatch
    ):
        """
        Testa workflow completo: Clone → Dubbing com voz clonada
        
        Valida:
        - Job de clonagem completa
        - VoiceProfile criado
        - Job de dubbing com voz clonada completa
        - Áudio final gerado
        """
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        # ETAPA 1: Clonagem
        clone_job = Job.create_new(
            mode=JobMode.CLONE_VOICE,
            voice_name="Complete Workflow Voice",
            source_language="pt",
            cache_ttl_hours=1
        )
        clone_job.input_file = reference_audio
        
        voice_profile = await processor_xtts.process_clone_job(clone_job)
        
        assert clone_job.status == JobStatus.COMPLETED
        assert voice_profile.id is not None
        
        # ETAPA 2: Dubbing com voz clonada
        dubbing_job = Job.create_new(
            mode=JobMode.DUBBING_WITH_CLONE,
            text="Este é um teste de workflow completo com XTTS.",
            source_language="pt",
            voice_id=voice_profile.id,
            cache_ttl_hours=1
        )
        
        result = await processor_xtts.process_dubbing_job(dubbing_job, voice_profile=voice_profile)
        
        # Valida resultado final
        assert result.status == JobStatus.COMPLETED
        assert result.output_file is not None
        assert os.path.exists(result.output_file)
        
        # Valida que são jobs diferentes
        assert clone_job.id != dubbing_job.id
        
        # Valida metadata
        assert result.duration > 0
        assert result.file_size_output > 0
    
    @pytest.mark.asyncio
    async def test_processor_performance_benchmark(
        self, processor_xtts, temp_output_dir, monkeypatch
    ):
        """
        Testa performance do processor com XTTS
        
        Valida:
        - Job completa em tempo razoável
        - RTF (Real-Time Factor) aceitável
        """
        import time
        
        monkeypatch.setitem(processor_xtts.settings, 'processed_dir', str(temp_output_dir))
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Este é um teste de performance para medir a velocidade de geração.",
            source_language="pt",
            cache_ttl_hours=1
        )
        
        start_time = time.time()
        result = await processor_xtts.process_dubbing_job(job)
        end_time = time.time()
        
        processing_time = end_time - start_time
        audio_duration = result.duration
        
        # RTF = processing_time / audio_duration
        rtf = processing_time / audio_duration if audio_duration > 0 else float('inf')
        
        print(f"\n📊 Performance Benchmark:")
        print(f"  Processing time: {processing_time:.2f}s")
        print(f"  Audio duration: {audio_duration:.2f}s")
        print(f"  RTF: {rtf:.2f}x")
        
        # RTF deve ser <10x em CPU (razoável)
        assert rtf < 10.0, f"RTF too high: {rtf:.2f}x (esperado <10x)"
        
        # Job deve completar
        assert result.status == JobStatus.COMPLETED
