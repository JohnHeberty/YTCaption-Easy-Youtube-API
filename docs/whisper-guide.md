# Guia Completo do OpenAI Whisper

## 🎙️ O que é o Whisper?

**Whisper** é um modelo de reconhecimento automático de fala (ASR - Automatic Speech Recognition) desenvolvido pela OpenAI, treinado em 680.000 horas de dados multilíngues e multitarefa coletados da web.

### Características Principais

- ✅ **Multilíngue**: Suporta 99+ idiomas
- ✅ **Robusto**: Funciona bem com áudio de baixa qualidade
- ✅ **Multitarefa**: Transcrição, tradução e identificação de idioma
- ✅ **Timestamps**: Fornece timestamps precisos por segmento
- ✅ **Open Source**: Código e modelos disponíveis publicamente

## 📊 Modelos Disponíveis

O Whisper oferece 6 modelos com diferentes trade-offs entre velocidade e precisão:

| Modelo | Parâmetros | VRAM Necessária | Velocidade Relativa | Uso Recomendado |
|--------|------------|-----------------|---------------------|-----------------|
| `tiny` | 39M | ~1 GB | ~10x | Testes rápidos, demos |
| `base` | 74M | ~1 GB | ~7x | Desenvolvimento, prototipagem |
| `small` | 244M | ~2 GB | ~4x | Produção com recursos limitados |
| `medium` | 769M | ~5 GB | ~2x | Boa precisão, performance aceitável |
| `large` | 1550M | ~10 GB | 1x | Máxima precisão |
| `turbo` | 809M | ~6 GB | ~8x | Otimizado para velocidade |

### Modelos English-Only

Para inglês, existem versões `.en` otimizadas:
- `tiny.en`, `base.en`, `small.en`, `medium.en`
- Geralmente têm melhor performance em inglês

### Nossa Escolha: `base`

Neste projeto, usamos o modelo **`base`** por padrão porque:

- ✅ Balance ideal entre velocidade e qualidade
- ✅ Requisitos de hardware moderados
- ✅ Adequado para produção com recursos limitados
- ✅ Suporta múltiplos idiomas

## 🔧 Como o Whisper Funciona

### Arquitetura

O Whisper é um modelo **Transformer sequence-to-sequence**:

```
┌─────────────┐
│ Audio Input │
└──────┬──────┘
       │
┌──────▼──────────────────┐
│ Mel Spectrogram (80ch)  │  ← Converte áudio em espectrograma
└──────┬──────────────────┘
       │
┌──────▼──────────────────┐
│ Encoder (Transformer)   │  ← Processa features de áudio
└──────┬──────────────────┘
       │
┌──────▼──────────────────┐
│ Decoder (Transformer)   │  ← Gera texto token por token
└──────┬──────────────────┘
       │
┌──────▼──────┐
│ Text Output │
└─────────────┘
```

### Processo de Transcrição

1. **Preprocessamento**:
   - Áudio é convertido para 16kHz mono
   - Normalização de amplitude
   - Divisão em janelas de 30 segundos

2. **Feature Extraction**:
   - Cria mel-spectrogram (80 canais)
   - Representa frequências ao longo do tempo

3. **Encoding**:
   - Encoder processa o espectrograma
   - Gera representações latentes

4. **Decoding**:
   - Decoder gera texto autoregressivamente
   - Usa attention mechanism
   - Produz timestamps para cada segmento

## 💻 Uso na Nossa API

### Inicialização

```python
from src.infrastructure.whisper import WhisperTranscriptionService

service = WhisperTranscriptionService(
    model_name="base",      # Modelo a usar
    device="cpu",           # 'cpu' ou 'cuda'
    compute_type="float32"  # Precisão computacional
)
```

### Transcrição

```python
# Transcrever com detecção automática de idioma
transcription = await service.transcribe(
    video_file=video_file,
    language="auto"
)

# Transcrever forçando idioma específico
transcription = await service.transcribe(
    video_file=video_file,
    language="pt"  # Português
)
```

### Detecção de Idioma

```python
language_code = await service.detect_language(video_file)
# Retorna: 'en', 'pt', 'es', etc.
```

## 🌍 Suporte a Idiomas

O Whisper suporta 99+ idiomas. Os principais incluem:

### Idiomas com Melhor Performance

| Código | Idioma | WER (Word Error Rate) |
|--------|--------|----------------------|
| `en` | English | ~5-10% |
| `zh` | Chinese | ~10-15% |
| `es` | Spanish | ~5-10% |
| `fr` | French | ~5-10% |
| `de` | German | ~5-10% |
| `pt` | Portuguese | ~10-15% |
| `ja` | Japanese | ~10-15% |
| `ko` | Korean | ~10-15% |

### Lista Completa de Códigos

```python
# Alguns dos idiomas suportados:
LANGUAGES = {
    'en': 'English',
    'pt': 'Portuguese',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'hi': 'Hindi',
    # ... e muitos mais
}
```

## ⚙️ Configuração e Otimização

### CPU vs GPU

**CPU (Padrão)**:
```python
device="cpu"
compute_type="float32"
```
- ✅ Funciona em qualquer máquina
- ❌ Mais lento (5-10x)
- ✅ Sem dependências de GPU

**GPU (CUDA)**:
```python
device="cuda"
compute_type="float16"  # Mais rápido em GPU
```
- ✅ Muito mais rápido
- ❌ Requer NVIDIA GPU
- ❌ Maior consumo de memória

### Otimizações de Performance

#### 1. Escolher Modelo Adequado

```python
# Para desenvolvimento/testes
model_name="tiny"  # Rápido, menos preciso

# Para produção
model_name="base"  # Balance ideal

# Para máxima qualidade
model_name="large"  # Lento, muito preciso
```

#### 2. Batch Processing

Para múltiplos arquivos:
```python
# Carregar modelo uma vez
service = WhisperTranscriptionService(model_name="base")

# Reusar para múltiplos arquivos
for video_file in video_files:
    transcription = await service.transcribe(video_file)
```

#### 3. Lazy Loading

Nosso serviço implementa lazy loading:
```python
def _load_model(self):
    if self._model is None:
        self._model = whisper.load_model(self.model_name)
    return self._model
```

Modelo é carregado apenas quando necessário!

### Gerenciamento de Memória

```python
# Limpar cache de GPU após uso
import torch
if torch.cuda.is_available():
    torch.cuda.empty_cache()
```

## 📝 Formato de Saída

### Estrutura de Segmento

```python
{
    "text": "Never gonna give you up",
    "start": 0.0,      # Segundos
    "end": 2.5,        # Segundos
    "duration": 2.5    # Calculado
}
```

### Transcrição Completa

```python
{
    "id": "uuid",
    "language": "en",
    "full_text": "Complete transcription...",
    "segments": [
        {"text": "...", "start": 0.0, "end": 2.5},
        {"text": "...", "start": 2.5, "end": 5.0},
        # ...
    ],
    "total_segments": 42,
    "duration": 213.5,
    "processing_time": 15.3
}
```

## 🎯 Casos de Uso

### 1. Transcrição de Podcasts

```python
# Áudio longo, boa qualidade
model_name="small"
language="auto"  # Detecta automaticamente
```

### 2. Legendas de Vídeos

```python
# Precisa de timestamps precisos
model_name="base"
# Usar segments com start/end
```

### 3. Transcrição Multilíngue

```python
# Vídeo com múltiplos idiomas
language="auto"  # Whisper detecta mudanças
```

### 4. Áudio de Baixa Qualidade

```python
# Chamadas telefônicas, conferências
model_name="medium"  # Mais robusto
```

## 🔍 Troubleshooting

### Erro: "Model not found"

```bash
# Modelos são baixados automaticamente na primeira execução
# Certifique-se de ter conexão com internet
# Cache: ~/.cache/whisper/
```

### Performance Lenta

```python
# 1. Usar modelo menor
model_name="tiny"  # Em vez de "large"

# 2. Usar GPU se disponível
device="cuda"

# 3. Processar arquivos menores
# Dividir áudio longo em chunks
```

### Erro de Memória

```python
# 1. Reduzir modelo
model_name="base"  # Em vez de "large"

# 2. Limpar cache
torch.cuda.empty_cache()

# 3. Processar em lotes menores
```

### Transcrição Incorreta

```python
# 1. Especificar idioma
language="pt"  # Em vez de "auto"

# 2. Usar modelo maior
model_name="medium"

# 3. Verificar qualidade do áudio
# Áudio muito ruidoso pode afetar precisão
```

## 📚 Recursos Adicionais

### Documentação Oficial

- **GitHub**: https://github.com/openai/whisper
- **Paper**: https://arxiv.org/abs/2212.04356
- **Blog Post**: https://openai.com/blog/whisper

### Ferramentas Relacionadas

- **faster-whisper**: Versão otimizada (2-4x mais rápido)
- **whisper.cpp**: Implementação em C++ (ainda mais rápido)
- **WhisperX**: Com alinhamento de palavras melhorado

### Comunidade

- **Discussões**: https://github.com/openai/whisper/discussions
- **Issues**: https://github.com/openai/whisper/issues

## 🎓 Melhores Práticas

### ✅ Faça

- ✅ Use o modelo adequado para seu caso
- ✅ Especifique o idioma quando conhecido
- ✅ Reutilize instâncias do modelo
- ✅ Monitore uso de memória
- ✅ Valide qualidade do áudio de entrada

### ❌ Evite

- ❌ Carregar modelo para cada transcrição
- ❌ Usar modelo muito grande desnecessariamente
- ❌ Ignorar erros de memória
- ❌ Processar áudio muito longo sem divisão
- ❌ Esquecer de limpar recursos

## 🚀 Próximos Passos

1. **Experimentar diferentes modelos**: Teste e compare performance
2. **Otimizar para seu caso**: Ajuste configurações
3. **Monitorar métricas**: Tempo de processamento, precisão
4. **Considerar GPU**: Se disponível, melhora muito
5. **Explorar fine-tuning**: Para casos muito específicos

---

**O Whisper é uma ferramenta poderosa para transcrição de áudio. Com as configurações corretas, você pode obter transcrições de alta qualidade para diversos casos de uso!**
