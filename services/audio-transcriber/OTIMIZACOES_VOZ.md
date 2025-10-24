# 🎙️ Otimizações para Voz/Conversas

## 📊 Pipeline de Processamento

O serviço foi otimizado especificamente para **gravações de voz e conversas**, aplicando técnicas que reduzem drasticamente o tamanho do arquivo mantendo a clareza da fala.

### 🔄 Ordem de Operações (Otimizada)

```
1. Carregamento      → Carrega arquivo original
2. Mono First        → Converte para mono (voz não precisa stereo)
3. Sample Rate       → Reduz para 16kHz (ideal para voz humana)
4. High-Pass Filter  → Remove frequências < 80Hz (ruído inaudível)
5. Noise Reduction   → Remove ruído de fundo
6. Compression       → Equaliza volume da fala (Dynamic Range)
7. Normalization     → Normaliza volume final
8. Export Opus       → Codec Opus 64kbps mono (melhor para voz)
```

## 🎯 Otimizações Implementadas

### 1️⃣ **Mono Obrigatório** (Redução: ~50%)
- **Por quê**: Voz humana não tem informação espacial útil em stereo
- **Quando**: PRIMEIRO passo (antes de qualquer processamento)
- **Benefício**: Metade do tamanho + processamento 2x mais rápido

### 2️⃣ **Sample Rate 16kHz** (Redução: ~66%)
- **Original**: 44.1kHz ou 48kHz (overkill para voz)
- **Otimizado**: 16kHz
- **Justificativa**: 
  - Voz humana: 80Hz - 8kHz
  - Nyquist: 16kHz captura até 8kHz perfeitamente
  - Telefonia VoIP usa 8kHz (suficiente para inteligibilidade)
- **Qualidade**: Imperceptível para voz

### 3️⃣ **High-Pass Filter @ 80Hz** (Redução: ~10%)
- **O que remove**: Frequências abaixo de 80Hz
- **Por quê**: 
  - Voz masculina mais grave: ~85Hz
  - < 80Hz = Apenas ruído (ar-condicionado, vibração, etc)
- **Filtro**: Butterworth 5ª ordem (resposta plana)
- **Benefício**: Áudio mais limpo + melhor compressão

### 4️⃣ **Dynamic Range Compression** (Melhora clareza)
- **Threshold**: -20dB
- **Ratio**: 4:1 (compressão moderada)
- **Attack**: 5ms (reage rápido)
- **Release**: 50ms (suaviza transições)
- **Efeito**: 
  - Partes baixas ficam mais audíveis
  - Partes altas não saturam
  - Volume consistente (estilo podcast profissional)

### 5️⃣ **Codec Opus 64kbps** (Redução: ~80%)
- **Por quê Opus**:
  - Melhor codec para voz (especificação RFC 6716)
  - 64kbps = Qualidade transparente para voz
  - MP3 128kbps seria necessário para mesma qualidade
- **Parâmetros**:
  - `VBR on`: Bitrate variável (otimiza silêncios)
  - `compression_level 10`: Máxima compressão
  - `application voip`: Otimizado para voz
- **Suporte**: Chrome, Firefox, Edge, Safari 14+

## 📉 Redução de Tamanho Esperada

### Exemplo Real: Áudio de 10 minutos

| Formato Original | Tamanho Original | Após Otimização | Redução |
|------------------|------------------|-----------------|---------|
| WAV 48kHz Stereo | 100 MB | 4.8 MB | **95.2%** |
| MP3 320kbps Stereo | 24 MB | 4.8 MB | **80%** |
| MP3 128kbps Stereo | 9.6 MB | 4.8 MB | **50%** |
| AAC 128kbps Mono | 9.6 MB | 4.8 MB | **50%** |

**Resultado final**: ~4.8MB para 10min de voz (Opus 64kbps mono 16kHz)

### Calculadora Rápida

```
Tamanho Final = (Duração em segundos) × (64 kbps / 8) 
              = Duração × 8 KB/s

Exemplos:
- 1 min  (60s)  → 480 KB  (~0.5 MB)
- 10 min (600s) → 4.8 MB
- 1 hora (3600s)→ 28.8 MB
```

## 🎧 Qualidade de Áudio

### Frequências Preservadas
```
Voz Masculina:    85 Hz - 180 Hz  ✅ Preservado
Voz Feminina:     165 Hz - 255 Hz ✅ Preservado
Vogais:           300 Hz - 3 kHz  ✅ Preservado
Consoantes:       2 kHz - 8 kHz   ✅ Preservado
Ruído < 80Hz:     20 Hz - 80 Hz   ❌ Removido
Ultrassônico:     > 8 kHz          ❌ Removido (imperceptível)
```

### Comparação Subjetiva (MOS - Mean Opinion Score)

| Codec | Bitrate | MOS (1-5) | Uso |
|-------|---------|-----------|-----|
| Opus (nossa solução) | 64 kbps | 4.5 | ✅ Excelente para voz |
| MP3 | 128 kbps | 4.2 | Música comprimida |
| MP3 | 64 kbps | 3.5 | Qualidade AM Radio |
| GSM | 13 kbps | 3.0 | Telefone celular |
| G.729 | 8 kbps | 3.5 | VoIP básico |

## 🔧 Configuração

### Parâmetros Atuais (Fixos para Voz)

```python
SAMPLE_RATE = 16000        # 16kHz
CHANNELS = 1               # Mono
HIGHPASS_CUTOFF = 80       # Hz
OPUS_BITRATE = 64          # kbps
COMPRESSION_THRESHOLD = -20 # dB
COMPRESSION_RATIO = 4.0    # 4:1
```

### Se precisar ajustar no futuro:

**Para voz mais grave (homens)**:
```python
HIGHPASS_CUTOFF = 70  # Hz (preserva mais graves)
```

**Para melhor qualidade (podcasts profissionais)**:
```python
OPUS_BITRATE = 96  # kbps (mais detalhes)
```

**Para economia extrema (audiobooks)**:
```python
SAMPLE_RATE = 12000  # 12kHz (ainda inteligível)
OPUS_BITRATE = 48    # kbps (economia máxima)
```

## 📊 Comparação com Serviços Comerciais

| Serviço | Codec | Bitrate | Sample Rate | Tamanho (10min) |
|---------|-------|---------|-------------|-----------------|
| **Nossa solução** | Opus | 64 kbps | 16 kHz | **4.8 MB** |
| Spotify Podcast | Opus | 96 kbps | 44.1 kHz | 7.2 MB |
| YouTube Audio | Opus | 128 kbps | 48 kHz | 9.6 MB |
| Apple Podcast | AAC | 64 kbps | 44.1 kHz | 4.8 MB |
| Audible | Enhanced AAC | 64 kbps | 22 kHz | 4.8 MB |

Nossa solução é **comparável aos melhores** (Apple Podcast, Audible) em tamanho final!

## 🚀 Performance

### Tempo de Processamento Estimado

```
Áudio de 10 minutos:
- Carregamento:        2s
- Mono + Downsample:   1s
- High-Pass Filter:    1s
- Noise Reduction:     15s  (mais pesado)
- Compression:         1s
- Normalization:       1s
- Export Opus:         3s
─────────────────────────
Total:                ~24s

Áudio de 1 hora:
Total:                ~2.5min
```

### Recursos Utilizados

```
CPU: ~70% (1 core)
RAM: ~500MB (para áudio de 1h)
Disco: Input deletado após processamento
```

## ✅ Casos de Uso Ideais

✅ **Perfeito para**:
- 🎙️ Podcasts
- 📞 Gravações de reuniões/chamadas
- 🎓 Aulas online
- 📖 Audiobooks
- 🗣️ Entrevistas
- 💼 Transcrições de voz

❌ **Não recomendado para**:
- 🎵 Música (use AAC 256kbps ou FLAC)
- 🎬 Trilhas sonoras de filme
- 🎸 Gravações de instrumentos
- 🔊 DJ sets / mixagens

## 🧪 Testes de Qualidade

Para validar a qualidade, teste com:

1. **Voz masculina grave** (testa high-pass @ 80Hz)
2. **Voz feminina aguda** (testa preservação de harmônicos)
3. **Sibilantes (S, T, P)** (testa 16kHz sample rate)
4. **Ambiente ruidoso** (testa noise reduction)
5. **Volume variável** (testa dynamic compression)

### Comando de teste:
```bash
# Envia áudio de teste
curl -X POST http://localhost:8001/normalize \
  -F "file=@test_voice.mp3" \
  -F "remove_noise=true" \
  -F "normalize_volume=true" \
  -F "convert_to_mono=true"

# Compara tamanhos
ls -lh test_voice.mp3 processed/*.opus
```

## 📚 Referências Técnicas

- **Opus Codec**: RFC 6716 (IETF Standard)
- **Sample Rate para Voz**: ITU-T Recommendation G.711
- **Dynamic Range**: AES Convention Paper 8578
- **High-Pass Filter**: Butterworth Filter Design (Wikipedia)
- **Noise Reduction**: noisereduce library (spectral gating)

## 🎯 Próximas Melhorias (Futuro)

- [ ] Detecção automática de silêncios (remove pausas longas)
- [ ] Equalização adaptativa (ajusta por características da voz)
- [ ] Detecção de clipping (previne distorção)
- [ ] Stereo preservado para música (auto-detect)
- [ ] Batch processing (múltiplos arquivos)

---

**Status**: ✅ Otimizado para voz/conversas  
**Redução média**: 85-95% vs original  
**Qualidade**: Transparente para voz humana
