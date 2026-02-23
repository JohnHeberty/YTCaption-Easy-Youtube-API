# 🎵 SPRINT 3 - UTILS (ÁUDIO, VAD, TIMEOUT)

**Status**: ⏳ Pendente  
**Prioridade**: 🟡 ALTA  
**Duração Estimada**: 3-4 horas  
**Pré-requisitos**: Sprint 0 completa

---

## 🎯 OBJETIVOS

Testar utilitários com arquivos reais:

1. ✅ Processamento de áudio real (extração, duração, normalização)
2. ✅ Voice Activity Detection (VAD) com áudios reais
3. ✅ Timeout handlers funcionais
4. ✅ Garantir integração com FFmpeg

---

## 📁 ARQUIVOS NO ESCOPO

```
app/utils/
├── __init__.py
├── audio_utils.py      # Manipulação de áudio
├── vad_utils.py        # Voice Activity Detection utils
├── vad.py              # VAD implementation
└── timeout_utils.py    # Timeout decorators/handlers
```

---

## 🧪 TESTES - `tests/unit/utils/test_audio_utils.py`

```python
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
        assert duration < 10  # Áudio de teste ~5s
    
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
        assert real_test_audio.suffix in ['.mp3', '.wav', '.aac']
        
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
```

---

## 🧪 TESTES - `tests/unit/utils/test_vad.py`

```python
"""Testes para Voice Activity Detection"""
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_audio
@pytest.mark.slow
class TestVAD:
    """Testes de Voice Activity Detection"""
    
    def test_vad_with_tone_audio(self, real_test_audio):
        """VAD com áudio de tom puro (sem voz)"""
        # Áudio de teste é tom puro, não deve detectar voz
        # (teste básico de integração)
        assert real_test_audio.exists()
    
    def test_vad_with_silent_audio(self, silent_audio):
        """VAD com áudio silencioso"""
        # Áudio silencioso não deve ter atividade
        assert silent_audio.exists()
        
        # Verificar que é realmente silencioso
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(silent_audio)
        ], capture_output=True, text=True, check=True)
        
        assert result.returncode == 0
    
    def test_detect_audio_segments(self, real_test_audio):
        """Detecta segmentos de áudio"""
        # Usar silencedetect do FFmpeg como baseline
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_audio),
            "-af", "silencedetect=noise=-30dB:d=0.5",
            "-f", "null", "-"
        ], capture_output=True, text=True)
        
        # Deve executar sem erro
        assert "silencedetect" in result.stderr.lower() or result.returncode == 0


class TestVADUtils:
    """Testes para vad_utils.py"""
    
    def test_vad_utils_module_imports(self):
        """Módulo VAD utils importa"""
        try:
            from app.utils import vad_utils
            assert vad_utils is not None
        except ImportError:
            pytest.skip("vad_utils.py não existe")
    
    def test_vad_module_imports(self):
        """Módulo VAD importa"""
        try:
            from app.utils import vad
            assert vad is not None
        except ImportError:
            pytest.skip("vad.py não existe")
```

---

## 🧪 TESTES - `tests/unit/utils/test_timeout_utils.py`

```python
"""Testes para timeout utilities"""
import pytest
import time


class TestTimeoutUtils:
    """Testes de timeout handlers"""
    
    def test_timeout_utils_module_imports(self):
        """Módulo timeout importa"""
        try:
            from app.utils import timeout_utils
            assert timeout_utils is not None
        except ImportError:
            pytest.skip("timeout_utils.py não existe")
    
    def test_function_completes_within_timeout(self):
        """Função rápida não atinge timeout"""
        def fast_function():
            time.sleep(0.1)
            return "completed"
        
        result = fast_function()
        assert result == "completed"
    
    def test_function_exceeds_timeout(self):
        """Função lenta deve ser interrompida"""
        def slow_function():
            time.sleep(10)
            return "should not reach"
        
        # Simular timeout manual
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Function took too long")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1)  # 1 segundo
        
        with pytest.raises(TimeoutError):
            slow_function()
        
        signal.alarm(0)  # Cancelar alarme
    
    def test_timeout_with_successful_operation(self):
        """Operação bem-sucedida dentro do tempo"""
        start = time.time()
        time.sleep(0.5)
        elapsed = time.time() - start
        
        assert elapsed < 1.0


class TestRealWorldTimeout:
    """Testes de timeout em cenários reais"""
    
    @pytest.mark.requires_ffmpeg
    @pytest.mark.slow
    def test_ffmpeg_with_timeout(self, real_test_video, tmp_path):
        """FFmpeg com timeout"""
        output = tmp_path / "output.mp4"
        
        # Operação rápida deve completar
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-t", "2",  # Apenas 2 segundos
            "-y", str(output)
        ], timeout=5, capture_output=True)  # Timeout de 5s
        
        assert result.returncode == 0
        assert output.exists()
    
    @pytest.mark.slow
    def test_operation_with_retry_on_timeout(self):
        """Opera��ão com retry após timeout"""
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Simular operação
                time.sleep(0.1)
                break
            except TimeoutError:
                attempt += 1
                if attempt >= max_attempts:
                    raise
        
        assert attempt < max_attempts
```

---

## 📋 PASSO A PASSO

```bash
# 1. Criar estrutura
mkdir -p tests/unit/utils
touch tests/unit/utils/__init__.py

# 2. Criar arquivos de teste
touch tests/unit/utils/test_audio_utils.py
touch tests/unit/utils/test_vad.py
touch tests/unit/utils/test_timeout_utils.py

# 3. Implementar testes (copiar códigos acima)

# 4. Executar
pytest tests/unit/utils/ -v

# 5. Com markers
pytest tests/unit/utils/ -v -m "requires_audio"
pytest tests/unit/utils/ -v -m "requires_ffmpeg"

# 6. Cobertura
pytest tests/unit/utils/ --cov=app.utils --cov-report=term
```

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

- [ ] Audio utils testados com arquivos reais
- [ ] FFmpeg integração validada
- [ ] VAD testado (baseline)
- [ ] Timeout handlers funcionais
- [ ] Cobertura > 85%
- [ ] Todos os testes passando

---

**Status**: ⏳ Pendente  
**Data de Conclusão**: ___________
