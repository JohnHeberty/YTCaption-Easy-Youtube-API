# Engines de Transcrição Whisper

## 🎯 Situação Atual

Atualmente **apenas Faster-Whisper** está implementado e funcionando.

### ✅ Implementado
- **faster-whisper** (padrão): 4x mais rápido que openai-whisper, word timestamps nativos

### ⚠️ Planejado (não implementado)
- **openai-whisper**: Original da OpenAI, mais lento mas compatível
- **whisperx**: Word-level timestamps com forced alignment (mais preciso)

## 📊 Comparação de Engines

| Feature | faster-whisper | openai-whisper | whisperx |
|---------|---------------|----------------|----------|
| **Status** | ✅ Implementado | ⚠️ Planejado | ⚠️ Planejado |
| **Velocidade** | 4x mais rápido | Baseline (1x) | Similar a faster |
| **Word timestamps** | ✅ Nativos | ❌ Requer patch | ✅ Forced alignment |
| **Precisão timestamps** | Boa | N/A | Excelente |
| **VRAM** | Baixo (~500MB) | Alto (~1.5GB) | Médio (~800MB) |
| **Dependências** | CTranslate2 | PyTorch | PyTorch + Phoneme |

## 🚀 Como Usar

### API REST

```bash
# Usando faster-whisper (padrão)
curl -X POST "http://localhost:8002/jobs" \
  -F "file=@audio.mp3" \
  -F "language_in=auto" \
  -F "engine=faster-whisper"

# Futuro: usando whisperx (quando implementado)
curl -X POST "http://localhost:8002/jobs" \
  -F "file=@audio.mp3" \
  -F "language_in=auto" \
  -F "engine=whisperx"
```

### Swagger UI (http://localhost:8002/docs)

1. Acesse `/docs`
2. Vá em `POST /jobs`
3. No campo `engine`, selecione:
   - `faster-whisper` (padrão, recomendado)
   - `openai-whisper` (futuro)
   - `whisperx` (futuro)

## 📦 Implementação Futura

### Para adicionar openai-whisper:

```bash
pip install openai-whisper
```

```python
# app/openai_whisper_manager.py
class OpenAIWhisperManager(IModelManager):
    def __init__(self):
        import whisper
        self.model = whisper.load_model("base")
    
    def transcribe(self, audio_path, language="auto"):
        result = self.model.transcribe(audio_path, language=language)
        return result
```

### Para adicionar whisperx:

```bash
pip install whisperx
```

```python
# app/whisperx_manager.py
class WhisperXManager(IModelManager):
    def __init__(self):
        import whisperx
        self.model = whisperx.load_model("base", device="cpu")
    
    def transcribe(self, audio_path, language="auto"):
        audio = whisperx.load_audio(audio_path)
        result = self.model.transcribe(audio)
        
        # Forced alignment para timestamps precisos
        model_a, metadata = whisperx.load_align_model(
            language_code=result["language"]
        )
        result = whisperx.align(
            result["segments"], 
            model_a, 
            metadata, 
            audio
        )
        return result
```

### Atualizar processor.py:

```python
def _load_model(self, engine: WhisperEngine):
    if engine == WhisperEngine.FASTER_WHISPER:
        self.model_manager = FasterWhisperModelManager()
    elif engine == WhisperEngine.OPENAI_WHISPER:
        self.model_manager = OpenAIWhisperManager()
    elif engine == WhisperEngine.WHISPERX:
        self.model_manager = WhisperXManager()
    
    self.model_manager.load_model()
```

## 🎯 Recomendações

### Use faster-whisper quando:
- ✅ Precisa de velocidade(4x mais rápido)
- ✅ Quer economizar VRAM
- ✅ Word timestamps são suficientes
- ✅ **Produção padrão** (é o que temos agora)

### Use whisperx quando (futuro):
- ✅ Precisa de timestamps MUITO precisos
- ✅ Fará alinhamento labial (lip-sync)
- ✅ Gerará legendas com timing perfeito
- ⚠️ Pode esperar um pouco mais (~20% mais lento)

### Use openai-whisper quando (futuro):
- ✅ Precisa de compatibilidade máxima
- ✅ Tem muito VRAM disponível
- ⚠️ Não tem pressa (4x mais lento)

## 📝 Status dos Testes

### Faster-Whisper ✅
- ✅ 6 testes reais passando (sem mocks)
- ✅ Transcrição validada com TEST-.ogg
- ✅ Word timestamps funcionando
- ✅ Performance medida: RTF ~1.7x no CPU

### OpenAI-Whisper ⚠️
- ⚠️ Não implementado
- 📋 Testes: A fazer

### WhisperX ⚠️
- ⚠️ Não implementado
- 📋 Testes: A fazer

## 🔧 Configuração

```bash
# .env
WHISPER_ENGINE=faster-whisper  # padrão
WHISPER_MODEL=small            # tiny, base, small, medium, large
WHISPER_DEVICE=cpu             # cpu, cuda
```

## 📚 Referências

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) - CTranslate2-based
- [OpenAI Whisper](https://github.com/openai/whisper) - Original
- [WhisperX](https://github.com/m-bain/whisperX) - Forced alignment
