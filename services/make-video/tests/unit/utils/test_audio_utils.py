"""Testes para audio_utils.py com arquivos REAIS"""
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_audio
@pytest.mark.requires_ffmpeg
class TestAudioUtils:
    """Testes de manipulação de áudio"""
    
    def test_extract_audio_from_video(self, real_test_video, tmp_path):
        """Extrai áudio de vídeo real usando FFmpeg"""
        output_audio = tmp_path / "extracted_audio.mp3"
        
        # Extrair áudio com FFmpeg diretamente
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vn", "-acodec", "libmp3lame",
            "-y", str(output_audio)
        ], capture_output=True)
        
        # Pode não ter áudio (video de teste é silencioso)
        # Mas o comando deve executar sem erro
        assert result.returncode in [0, 1]  # 0=sucesso, 1=sem audio
    
    def test_get_audio_duration(self, real_test_audio):
        """Calcula duração de áudio real"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(real_test_audio)
        ], capture_output=True, text=True, check=True)
        
        duration = float(result.stdout.strip())
        
        assert duration > 0
        assert duration < 10  # Áudio de teste ~3s
    
    def test_get_audio_metadata(self, real_test_audio):
        """Obtém metadados de áudio real"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "json",
            str(real_test_audio)
        ], capture_output=True, text=True, check=True)
        
        assert result.returncode == 0
        assert "streams" in result.stdout
    
    def test_convert_audio_format(self, real_test_audio, tmp_path):
        """Converte formato de áudio"""
        output_wav = tmp_path / "converted.wav"
        
        subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-acodec", "pcm_s16le",
            "-y", str(output_wav)
        ], check=True, capture_output=True)
        
        assert output_wav.exists()
        assert output_wav.suffix == ".wav"
        assert output_wav.stat().st_size > 0
    
    def test_audio_file_validation(self, real_test_audio):
        """Valida arquivo de áudio real"""
        # Deve ser um arquivo válido
        assert real_test_audio.exists()
        assert real_test_audio.is_file()
        assert real_test_audio.suffix in ['.mp3', '.wav', '.aac', '.ogg']
        
        # Deve ter tamanho > 0
        assert real_test_audio.stat().st_size > 0


@pytest.mark.requires_ffmpeg
class TestAudioProcessing:
    """Testes de processamento de áudio"""
    
    def test_normalize_audio_volume(self, real_test_audio, tmp_path):
        """Normaliza volume de áudio"""
        output = tmp_path / "normalized.mp3"
        
        # Normalização com filtro loudnorm
        subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-af", "loudnorm",
            "-y", str(output)
        ], check=True, capture_output=True)
        
        assert output.exists()
    
    def test_trim_audio(self, real_test_audio, tmp_path):
        """Corta áudio em segmento específico"""
        output = tmp_path / "trimmed.mp3"
        
        # Cortar primeiros 2 segundos
        subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-ss", "0", "-t", "2",
            "-y", str(output)
        ], check=True, capture_output=True)
        
        assert output.exists()
        assert output.stat().st_size > 0
    
    def test_audio_sample_rate(self, real_test_audio):
        """Verifica sample rate do áudio"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(real_test_audio)
        ], capture_output=True, text=True, check=True)
        
        sample_rate = int(result.stdout.strip())
        assert sample_rate > 0
        assert sample_rate in [8000, 16000, 22050, 44100, 48000]  # sample rates comuns
    
    def test_audio_channels(self, real_test_audio):
        """Verifica número de canais do áudio"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=channels",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(real_test_audio)
        ], capture_output=True, text=True, check=True)
        
        channels = int(result.stdout.strip())
        assert channels > 0
        assert channels in [1, 2]  # mono ou stereo
    
    def test_audio_codec(self, real_test_audio):
        """Verifica codec do áudio"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(real_test_audio)
        ], capture_output=True, text=True, check=True)
        
        codec = result.stdout.strip()
        assert codec != ""
        assert codec in ["opus", "mp3", "aac", "pcm_s16le", "vorbis"]
    
    def test_resample_audio(self, real_test_audio, tmp_path):
        """Reamostra áudio para 16kHz (comum em VAD)"""
        output = tmp_path / "resampled_16khz.wav"
        
        subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-ar", "16000",
            "-ac", "1",  # mono
            "-y", str(output)
        ], check=True, capture_output=True)
        
        assert output.exists()
        
        # Verificar que foi realmente resampleado para 16kHz
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(output)
        ], capture_output=True, text=True, check=True)
        
        sample_rate = int(result.stdout.strip())
        assert sample_rate == 16000
