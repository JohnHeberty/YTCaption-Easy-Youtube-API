# 🎤 Isolamento de Voz (Vocal Isolation)

## 📋 Visão Geral

Agora o serviço pode **isolar a voz** removendo completamente o instrumental, usando **Spleeter** (Deezer AI).

## 🎯 Para Que Serve

### Cenário: Música "xiada" com fundo musical

```
❌ Problema:
- Baixou áudio de música
- Quer só a voz do cantor
- Instrumental atrapalha a transcrição

✅ Solução:
- isolate_vocals=true
- Remove TUDO exceto a voz
- Perfeito para karaoke, covers, transcrição
```

## 🔧 Como Usar

### Endpoint com Nova Opção

```bash
POST /normalize
  file: musica.mp3
  isolate_vocals: true   # NOVO! Remove instrumental
  remove_noise: true
  normalize_volume: true
  convert_to_mono: true
```

### Exemplo cURL

```bash
# Upload de música
curl -X POST http://localhost:8001/normalize \
  -F "file=@musica.mp3" \
  -F "isolate_vocals=true" \
  -F "remove_noise=true" \
  -F "normalize_volume=true" \
  -F "convert_to_mono=true"

# Resposta
{
  "id": "abc123def_invm",  # 'i' = isolate vocals
  "status": "queued",
  "progress": 0.0
}
```

## 🔄 Pipeline de Processamento

### Com `isolate_vocals=true`:

```
1. Upload: musica.mp3 (voz + instrumental)
           ↓
2. Demucs: Separa em vocals.wav + drums.wav + bass.wav + other.wav
           ↓
3. Seleciona: Apenas vocals.wav (descarta resto)
           ↓
4. Mono: Converte para mono
           ↓
5. 16kHz: Reduz sample rate
           ↓
6. High-Pass: Remove < 80Hz
           ↓
7. Noise Reduction: Remove ruído residual
           ↓
8. Compression: Equaliza volume
           ↓
9. Normalization: Volume consistente
           ↓
10. Export: voz_isolada.opus (só voz, sem música)
```

### Sem `isolate_vocals=false` (padrão):

```
1. Upload: gravacao_voz.mp3
           ↓
2. Processamento direto (pula Spleeter)
           ↓
3-9. Mesmos passos (mono, 16kHz, filter, noise, etc)
           ↓
10. Export: voz_processada.opus
```

## 📊 Tecnologia: Demucs (Meta AI)

### O que é Demucs?

- **Desenvolvido por**: Meta AI / Facebook Research (2021)
- **Modelo**: htdemucs (hybrid transformer)
- **Separação**: 4-stems (vocals, drums, bass, other)
- **Qualidade**: Estado-da-arte (melhor que Spleeter)
- **Tamanho**: ~350MB de modelo pré-treinado
- **Velocidade**: ~30-90s para processar 1 música (sem GPU)
- **Python**: Compatible com 3.11+

### Como Funciona?

```
Áudio Original (Stereo)
         ↓
     [Demucs]
         ↓
    ┌────┼────┐
    ↓    ↓    ↓    ↓
Vocals Drums Bass Other
(voz) (bateria)(baixo)(resto)
    ↓    ↓    ↓    ↓
Mantém Descarta Descarta Descarta
```

## ⚡ Performance

### Tempo de Processamento

| Duração Áudio | Sem Isolate | Com Isolate | Overhead |
|---------------|-------------|-------------|----------|
| 30 segundos | ~5s | ~20s | +15s |
| 3 minutos (música) | ~15s | ~45s | +30s |
| 10 minutos | ~50s | ~2.5min | +1.5min |

**Nota**: Spleeter é a etapa mais lenta do pipeline

### Recursos Utilizados

```
CPU: ~80% (1 core)
RAM: ~2GB (durante Demucs)
Disco: +350MB (modelo Demucs)
Temp: +15MB por job (vocals.wav temporário)
```

## 🎯 Casos de Uso

### ✅ Ideal para:

1. **Karaoke**: Remover voz do cantor original
2. **Cover/Remix**: Isolar vocal para nova mixagem
3. **Transcrição**: Melhorar precisão removendo música
4. **Análise de Voz**: Estudar características vocais
5. **Podcast Mixado**: Separar voz de trilha de fundo
6. **Sampling**: Extrair vocals para usar em outra música

### ❌ Não recomendado para:

1. **Gravação de voz pura**: Use `isolate_vocals=false` (mais rápido)
2. **Podcast sem música**: Desnecessário (já é só voz)
3. **Audiobook**: Não tem instrumental para remover
4. **Real-time**: Spleeter demora ~30-60s

## 📉 Qualidade da Separação

### Expectativas Realistas

**Bom resultado** (SDR > 6dB):
- ✅ Voz bem destacada do instrumental
- ✅ Pop, Rock, Hip-Hop comercial
- ✅ Gravações de estúdio

**Resultado aceitável** (SDR 3-6dB):
- ⚠️ Voz com leve "eco" do instrumental
- ⚠️ Música ao vivo
- ⚠️ Gravações antigas/mono

**Resultado ruim** (SDR < 3dB):
- ❌ Música eletrônica pesada
- ❌ Metal extremo (blast beats)
- ❌ Voz muito processada/autotune

**SDR** = Signal-to-Distortion Ratio (quanto maior, melhor)

## 🔀 Comparação: Com vs Sem Isolamento

### Exemplo: "Hotel California" (Eagles)

```
Original: 6.9MB WEBM (voz + instrumental)

Sem isolate_vocals:
├─ Output: 1.5MB Opus
├─ Tempo: ~15s
└─ Conteúdo: Voz + Música (tudo)

Com isolate_vocals:
├─ Output: 1.4MB Opus
├─ Tempo: ~45s
└─ Conteúdo: Só voz (música removida)
```

## 🎧 Qualidade do Resultado

### Formato de Saída (Idêntico):
- **Codec**: Opus 64kbps
- **Sample Rate**: 16kHz
- **Channels**: Mono
- **Formato**: `.opus`

### Diferença de Qualidade:
```
isolate_vocals=false → Voz + Música juntas
isolate_vocals=true  → Só voz (mais limpa para transcrição)
```

## 💡 Dicas de Uso

### 1. **Quando usar `isolate_vocals=true`**

```bash
# Música baixada do YouTube
curl -X POST http://localhost:8001/normalize \
  -F "file=@musica_youtube.webm" \
  -F "isolate_vocals=true"  # REMOVE instrumental
```

### 2. **Quando usar `isolate_vocals=false`** (padrão)

```bash
# Gravação de voz pura (reunião, podcast)
curl -X POST http://localhost:8001/normalize \
  -F "file=@reuniao.mp3" \
  -F "isolate_vocals=false"  # Processamento rápido
```

### 3. **Cache funciona**

```bash
# Primeira vez: processa com Spleeter (~45s)
POST /normalize file=musica.mp3 isolate_vocals=true
→ Job ID: abc123_invm

# Segunda vez com MESMO arquivo: retorna cache (instantâneo)
POST /normalize file=musica.mp3 isolate_vocals=true
→ Job ID: abc123_invm (mesmo hash!)
```

## 🔤 Job ID com Isolamento

### Formato do Job ID:

```
hash_operacoes

Exemplo:
f544be585c84_invm

Onde:
- f544be585c84 = Hash SHA256 do arquivo (12 chars)
- i = isolate_vocals
- n = remove_noise
- v = normalize_volume
- m = convert_to_mono (always true)
```

### Códigos de Operação:

| Código | Operação | Padrão |
|--------|----------|--------|
| `i` | isolate_vocals | false |
| `n` | remove_noise | true |
| `v` | normalize_volume | true |
| `m` | convert_to_mono | true |

## 🐛 Troubleshooting

### Erro: "Demucs model download failed"

**Causa**: Primeira execução precisa baixar modelo (~350MB)

**Solução**:
```bash
# Aguarde o download completar (automático na primeira vez)
# Ou baixe manualmente:
docker exec audio-normalization-celery python -c "from demucs.pretrained import get_model; get_model('htdemucs')"
```

### Erro: "MemoryError"

**Causa**: Áudio muito longo (> 30min)

**Solução**:
```bash
# Corte em pedaços menores
ffmpeg -i long_audio.mp3 -ss 0 -t 600 part1.mp3  # 10min
curl -F "file=@part1.mp3" ...
```

### Slow Performance

**Causa**: CPU fraca, Demucs é computacionalmente pesado

**Soluções**:
1. Use `isolate_vocals=false` se não precisar
2. Aguarde ~1-3min por música de 3min
3. Considere GPU (10x mais rápido) para produção

## 📚 Referências

- **Demucs GitHub**: https://github.com/facebookresearch/demucs
- **Paper**: "Hybrid Spectrogram and Waveform Source Separation" (Meta AI, 2021)
- **Alternativas**: Spleeter (mais leve, qualidade inferior), MDX-Net (meio termo)

## 🎯 Roadmap Futuro

Possíveis melhorias:

- [ ] GPU support (10x mais rápido)
- [ ] Modelo Demucs v5 (quando lançar)
- [ ] Opção de manter 4-stems separados (vocals, bass, drums, other)
- [ ] Streaming (processar enquanto baixa)
- [ ] Preview (primeiros 30s para testar)

---

**Status**: ✅ Implementado com Demucs htdemucs  
**Performance**: ~30-90s para música de 3min  
**Qualidade**: Estado-da-arte (melhor que Spleeter)
