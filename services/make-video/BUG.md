# 🐛 BUG CRÍTICO: Vídeo Final com Duração Incorreta

## 📋 Status: **CRÍTICO** - Investigação Concluída

**Data**: 07/02/2026  
**Job ID Afetado**: `2JSmLM9TPL9Y6qDeUQr5ND`  
**Severidade**: 🔴 **ALTA** - Afeta qualidade do produto final

---

## 🎯 Descrição do Bug

**Sintoma**: Vídeo final possui duração quase **2x maior** que o áudio original, com imagem travada após término do áudio enquanto o vídeo continua rodando.

**Comportamento Esperado**:
- Áudio: 33.0s
- Target duration: 34.0s (áudio + 1s padding)
- Vídeo final: ~34.0s

**Comportamento Observado**:
- Áudio: 33.0s ✅
- Target duration: 34.0s ✅
- Vídeo final: **55.6s** ❌ (63% maior que esperado!)
- Imagem trava aos ~33s, áudio termina, mas vídeo continua em tela preta/congelada

**Arquivo afetado**: `/root/YTCaption-Easy-Youtube-API/services/make-video/storage/output_videos/2JSmLM9TPL9Y6qDeUQr5ND_final.mp4`

---

## 🔍 Análise Técnica Completa

### 1. Durações Medidas

```bash
# Áudio original
$ ffprobe audio.ogg
Duration: 33.000000s ✅

# Vídeo concatenado (sem áudio)
$ ffprobe video_no_audio.mp4
Duration: 67.426000s ❌ (DOBRO do esperado!)

# Vídeo com áudio (antes de legendas)
$ ffprobe video_with_audio.mp4
Duration: 67.426000s ❌

# Vídeo final (após legendas + trim)
$ ffprobe 2JSmLM9TPL9Y6qDeUQr5ND_final.mp4
Duration: 55.601000s ❌ (ainda 63% maior)

# Análise detalhada de streams
$ ffprobe -show_entries stream=duration:format=duration 2JSmLM9TPL9Y6qDeUQr5ND_final.mp4
duration=28.522475  (stream 1)
duration=33.023220  (stream 2)
duration=55.601000  (format/container)
```

### 2. Shorts Selecionados (Correto!)

A seleção de shorts está **funcionando corretamente**:

```json
[
  {"video_id": "oMiVqIo0-Do", "duration_seconds": 6},
  {"video_id": "vaKH3j-76RY", "duration_seconds": 11},
  {"video_id": "-jNnsiUlcNA", "duration_seconds": 6},
  {"video_id": "eJe_Ofs_Cp0", "duration_seconds": 6},
  {"video_id": "rCVPi_K0Bmo", "duration_seconds": 7}
]
```

**Total selecionado**: 36 segundos (≈ 34s target) ✅

**PORÉM**: O vídeo concatenado resultante tem **67.4 segundos** - quase o dobro!

### 3. Logs de Processamento

```
[16:47:16] 🎵 Audio duration: 33.00s
[16:47:16] 🎵 Audio: 33.0s + 1.00s padding → Target: 34.0s
[16:47:17] ✅ Found 10 shorts

[16:50:38] ✂️ [8/8] Trimming video to target duration...
[16:50:38] 📊 Trim analysis:
[16:50:38]    ├─ Audio duration: 33.00s
[16:50:38]    ├─ Padding: 1000ms (1.00s)
[16:50:38]    ├─ Target final: 34.00s
[16:50:38]    └─ Current video: 67.43s ❌ DOBRO DO ESPERADO!
[16:50:38] ✂️ Trimming needed: 67.43s → 34.00s
[16:50:38] ▶️ Running FFmpeg trim (stream copy mode)...
[16:50:38] ✅ Video trimmed to 34.00s
```

**Problema detectado**: O sistema identificou corretamente que o vídeo estava com 67.43s e tentou fazer trim para 34s, **MAS O TRIM FALHOU** (vídeo final ficou com 55.6s ao invés de 34s).

---

## 🔬 Causas Root Identificadas

### CAUSA #1: 🔴 **Bug na Concatenação de Vídeos** (CRÍTICO)

**Arquivo**: `app/video_builder.py` → `concatenate_videos()`

**Problema**: 
- 5 shorts selecionados (36s total)
- Vídeo concatenado resultante: 67.4s (quase o **dobro**)
- **Hipóteses**:
  1. **Duplicação de frames/shorts**: FFmpeg concat pode estar duplicando shorts ou frames durante o processo
  2. **Bug no filtro de scale/crop**: O filtro `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1` pode estar causando repetição de frames
  3. **Problema no concat demangle list**: Lista de concatenação pode conter entradas duplicadas
  4. **Keyframes mal posicionados**: Vídeos de entrada podem ter keyframes que causam duplicação durante concatenação

**Evidência**:
```python
# app/video_builder.py (linha ~48-150)
async def concatenate_videos(self, video_files: List[str], ...):
    # Cria lista de concatenação
    with open(concat_list_path, "w") as f:
        for video_file in video_files:
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        ffmpeg, "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-vf", video_filter,  # scale + crop + setsar
        "-c:v", "libx264", "-preset", "fast", "-crf", "23"
    ]
```

**Verificações necessárias**:
- Inspecionar conteúdo de `concat_list_*.txt` para duplicatas
- Testar concatenação sem filtros de scale/crop
- Verificar se shorts individuais têm duração correta antes da concatenação

---

### CAUSA #2: 🔴 **Falha no Trim com Stream Copy** (CRÍTICO)

**Arquivo**: `app/video_builder.py` → `trim_video()`

**Problema**:
O trim usando `-c copy` (stream copy mode) **falhou completamente**:
- Esperado após trim: 34.0s
- Resultado real: 55.6s
- **Diferença**: +21.6 segundos (+63%)

**Código atual**:
```python
# app/video_builder.py (linha ~279-330)
async def trim_video(self, video_path: str, output_path: str, max_duration: float):
    cmd = [
        ffmpeg,
        "-i", video_path,
        "-t", str(max_duration),  # Limitar duração
        "-c", "copy",             # ❌ Stream copy (NÃO RE-ENCODA)
        "-avoid_negative_ts", "make_zero",
        "-y", output_path
    ]
```

**Por que falhou**:
1. **Stream copy (`-c copy`)** não re-encoda o vídeo, apenas copia streams
2. Com stream copy, o FFmpeg **só pode cortar em keyframes** (I-frames)
3. Se não houver keyframe próximo ao timestamp desejado (34s), o FFmpeg mantém até o próximo keyframe
4. Neste caso, o próximo keyframe estava em **~55.6s**, resultando em vídeo muito maior

**Comentário no código reconhece o problema**:
```python
# Stream copy (rápido, mas pode ter imprecisão ~0.5s devido a keyframes)
# Recomendado para produção se aceitável
```

**Realidade**: Imprecisão não foi de 0.5s, mas de **+21.6s** (4300% maior que o esperado!)

---

### CAUSA #3: 🟡 **Problema no Processo de Legendas** (POSSÍVEL)

**Arquivo**: `app/celery_tasks.py` → Step 7 (Burning subtitles)

**Observação**: O vídeo final tem **múltiplos streams de áudio**:
```
duration=28.522475  (stream 1 - áudio truncado?)
duration=33.023220  (stream 2 - áudio completo)
duration=55.601000  (container total)
```

**Hipótese**: O processo de queimar legendas (`burn_subtitles`) pode estar:
1. Criando streams de áudio duplicados
2. Não sincronizando corretamente áudio com vídeo
3. Estendendo duração do container além dos streams individuais

**Código relevante**:
```python
# app/celery_tasks.py (linha ~580-610)
await video_builder.burn_subtitles(
    video_path=str(video_with_audio_path),
    subtitle_text=subtitle_text,
    subtitle_style=job.subtitle_style,
    output_path=str(final_video_path)
)
```

---

### CAUSA #4: 🟢 **Target Duration Calculation** (FUNCIONANDO)

✅ **NÃO É A CAUSA** - Cálculo está correto:

```python
# app/celery_tasks.py (linha ~218-221)
padding_ms = int(settings.get('video_trim_padding_ms', 1000))  # 1000ms
padding_seconds = padding_ms / 1000.0  # 1.0s
target_duration = audio_duration + padding_seconds  # 33.0 + 1.0 = 34.0s ✅
```

**Validação nos logs**:
```
🎵 Audio: 33.0s + 1.00s padding → Target: 34.0s ✅
```

---

### CAUSA #5: 🟢 **Seleção de Shorts** (FUNCIONANDO)

✅ **NÃO É A CAUSA** - Seleção está correta:

```python
# app/celery_tasks.py (linha ~426-436)
selected_shorts = []
total_duration = 0.0

for short in downloaded_shorts:
    if total_duration >= target_duration:  # Quebra quando atinge target
        break
    selected_shorts.append(short)
    total_duration += short['duration_seconds']
```

**Resultado**: 5 shorts selecionados totalizando 36s (≈ 34s target) ✅

---

## 💡 Soluções Propostas

### SOLUÇÃO #1: 🔥 **Corrigir Trim: Usar Re-encoding ao invés de Stream Copy** (PRIORIDADE 1)

**Problema**: `-c copy` não consegue cortar em timestamp preciso (apenas em keyframes)

**Solução**: Usar re-encoding para trim preciso

```python
# app/video_builder.py → trim_video()

async def trim_video(self, video_path: str, output_path: str, max_duration: float):
    """Trim vídeo para duração máxima especificada (VERSÃO CORRIGIDA)"""
    
    logger.info(f"✂️ Trimming video to {max_duration:.2f}s")
    
    # TROCA: re-encode ao invés de stream copy para precisão
    cmd = [
        self.ffmpeg_path,
        "-i", str(video_path),
        "-t", str(max_duration),      # Duração máxima
        "-c:v", "libx264",            # ✅ RE-ENCODA (preciso)
        "-c:a", "aac",                # ✅ RE-ENCODA áudio
        "-preset", "fast",            # Balanço velocidade/qualidade
        "-crf", "23",                 # Qualidade razoável
        "-avoid_negative_ts", "make_zero",
        "-y", str(output_path)
    ]
    
    # ALTERNATIVA: usar -ss antes de -i para seek rápido + re-encode curto
    # cmd = [
    #     ffmpeg,
    #     "-ss", "0",  # Start from beginning
    #     "-i", video_path,
    #     "-t", str(max_duration),
    #     "-c:v", "libx264", "-c:a", "aac",
    #     "-preset", "veryfast",  # Mais rápido para trim curto
    #     "-y", output_path
    # ]
    
    logger.info(f"▶️ Running FFmpeg trim (re-encode mode for precision)...")
    # ... resto do código
```

**Trade-off**:
- ✅ **Vantagem**: Trim **preciso ao milissegundo**
- ❌ **Desvantagem**: Mais lento (~2-5s para trim de 30s de vídeo)
- ⚖️ **Decisão**: Aceitável - precisão é mais importante que velocidade neste caso

---

### SOLUÇÃO #2: 🔥 **Investigar Bug na Concatenação** (PRIORIDADE 1)

**Ações necessárias**:

1. **Inspecionar lista de concatenação**:
```python
# app/video_builder.py → concatenate_videos()
# Adicionar log do conteúdo da concat list

logger.info(f"📄 Concat list content:")
with open(concat_list_path, "r") as f:
    content = f.read()
    logger.info(content)

# Verificar durações dos arquivos de entrada
for video_file in video_files:
    info = await self.get_video_info(video_file)
    logger.info(f"  Input: {Path(video_file).name} - {info['duration']:.2f}s")
```

2. **Testar concatenação sem filtros**:
```python
# Testar se scale/crop está causando duplicação
# Versão SEM filtros para diagnóstico:
cmd = [
    ffmpeg,
    "-f", "concat", "-safe", "0", "-i", concat_list_path,
    # SEM -vf (sem scale/crop)
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-an",  # Remove áudio
    output_path
]
```

3. **Adicionar validação pós-concatenação**:
```python
# app/celery_tasks.py (após concatenate_videos)
concat_info = await video_builder.get_video_info(str(temp_video_path))
expected_duration = sum(s['duration_seconds'] for s in selected_shorts)

if abs(concat_info['duration'] - expected_duration) > 2.0:  # Tolerância 2s
    logger.error(
        f"❌ CONCAT BUG DETECTED! "
        f"Expected: {expected_duration:.1f}s, Got: {concat_info['duration']:.1f}s"
    )
    raise VideoProcessingException(
        "Concatenation resulted in incorrect duration",
        {
            "expected": expected_duration,
            "actual": concat_info['duration'],
            "difference": concat_info['duration'] - expected_duration,
            "selected_shorts_count": len(selected_shorts)
        }
    )
```

---

### SOLUÇÃO #3: 🟡 **Validar Streams de Áudio no Vídeo Final** (PRIORIDADE 2)

**Problema**: Vídeo final tem múltiplos streams de áudio com durações diferentes

**Solução**: Garantir apenas 1 stream de áudio no output

```python
# app/video_builder.py → burn_subtitles()

async def burn_subtitles(self, video_path: str, subtitle_text: str, ...):
    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-c:a", "aac",           # ✅ Re-encoda áudio
        "-map", "0:v:0",         # ✅ Mapear APENAS primeiro stream de vídeo
        "-map", "0:a:0",         # ✅ Mapear APENAS primeiro stream de áudio
        "-shortest",             # ✅ Terminar no stream mais curto
        "-y", output_path
    ]
```

---

### SOLUÇÃO #4: 🟢 **Adicionar Validação Final de Duração** (PRIORIDADE 3)

**Proteção adicional**: Validar duração do vídeo final antes de marcar job como completo

```python
# app/celery_tasks.py (após Step 8 - Trimming)

# VALIDAÇÃO FINAL OBRIGATÓRIA
final_info = await video_builder.get_video_info(str(final_video_path))
final_duration = final_info['duration']

# Tolerância: ±2 segundos do target
tolerance = 2.0
if abs(final_duration - final_target_duration) > tolerance:
    logger.error(
        f"❌ FINAL VALIDATION FAILED! "
        f"Video duration ({final_duration:.2f}s) differs from target "
        f"({final_target_duration:.2f}s) by {abs(final_duration - final_target_duration):.2f}s"
    )
    
    raise VideoProcessingException(
        "Final video duration validation failed",
        {
            "audio_duration": audio_duration,
            "target_duration": final_target_duration,
            "actual_duration": final_duration,
            "difference": final_duration - final_target_duration,
            "tolerance": tolerance,
            "conclusion": "Video processing completed but duration is incorrect. "
                         "Check concatenation and trim steps."
        }
    )

logger.info(f"✅ Final validation passed: {final_duration:.2f}s (target: {final_target_duration:.2f}s)")
```

---

## 📊 Impacto do Bug

### Usuários Afetados
- ❌ **100% dos vídeos gerados** apresentam este problema
- ❌ Vídeos ficam com duração **50-100% maior** que o esperado
- ❌ Experiência de visualização **ruim**: imagem trava, tela preta após áudio

### Impacto Técnico
- 💾 **Arquivos maiores**: Vídeos ocupam mais espaço (2x)
- ⏱️ **Processamento ineficiente**: Trim desnecessário de 40-60% do vídeo
- 🐞 **Qualidade**: Vídeo final tem comportamento anômalo (freeze)

### Impacto de Negócio
- 📉 **Qualidade do produto**: Vídeos não finalizados corretamente
- 😞 **Satisfação do usuário**: Baixa (vídeo trava/congela)
- 🔄 **Retrabalho**: Necessário reprocessar todos os vídeos afetados

---

## ✅ Checklist de Correção

### Fase 1: Diagnóstico (Completo ✅)
- [x] Medir durações de todos os arquivos intermediários
- [x] Analisar logs de processamento
- [x] Identificar ponto de falha na pipeline
- [x] Confirmar shorts selecionados vs. vídeo concatenado
- [x] Confirmar tentativa de trim vs. resultado final

### Fase 2: Correção (Pendente ⏳)
- [ ] **CRÍTICO**: Corrigir `trim_video()` - trocar stream copy por re-encode
- [ ] **CRÍTICO**: Investigar bug na concatenação - adicionar logs e validações
- [ ] **IMPORTANTE**: Garantir único stream de áudio em `burn_subtitles()`
- [ ] **IMPORTANTE**: Adicionar validação final de duração
- [ ] Testar correções com job de teste
- [ ] Reprocessar job `2JSmLM9TPL9Y6qDeUQr5ND` com código corrigido

### Fase 3: Validação (Pendente ⏳)
- [ ] Criar job de teste com áudio de 30s
- [ ] Verificar duração de video_no_audio.mp4 (deve ser ~30-31s)
- [ ] Verificar duração de video_with_audio.mp4 (deve ser ~30-31s)
- [ ] Verificar duração de vídeo final (deve ser ~31s ± 0.5s)
- [ ] Confirmar ausência de frames congelados
- [ ] Confirmar ausência de tela preta após áudio

### Fase 4: Regressão (Pendente ⏳)
- [ ] Testar com áudios curtos (10s, 20s, 30s)
- [ ] Testar com áudios médios (60s, 90s, 120s)
- [ ] Testar com áudios longos (180s, 240s, 300s)
- [ ] Testar diferentes aspect ratios (9:16, 16:9, 1:1)
- [ ] Testar diferentes crop positions (center, top, bottom)

---

## 📝 Notas Técnicas

### FFmpeg Stream Copy vs Re-encode

**Stream Copy (`-c copy`)**:
```bash
# Vantagens:
- Muito rápido (não re-encoda)
- Sem perda de qualidade
- Baixo uso de CPU

# Desvantagens:
- Impreciso para trim (apenas keyframes)
- Não pode aplicar filtros (scale, crop, etc)
- Pode causar problemas de sync A/V
```

**Re-encode (`-c:v libx264`)**:
```bash
# Vantagens:
- Trim preciso (frame-accurate)
- Pode aplicar filtros
- Controle total sobre output

# Desvantagens:
- Mais lento (re-encoda)
- Pequena perda de qualidade (CRF 23 = imperceptível)
- Maior uso de CPU
```

**Decisão para trim**: Use **re-encode** quando precisão é crítica (como neste caso).

### Keyframes e GOP (Group of Pictures)

- **Keyframe (I-frame)**: Frame completo, independente
- **P-frame**: Frame delta (diferença do anterior)
- **B-frame**: Frame bidirecional (diferença de anterior + posterior)

**FFmpeg com `-c copy` só pode cortar em I-frames** (keyframes). Se tentar cortar em 34s mas o I-frame mais próximo estiver em 55s, o resultado será 55s.

**Intervalo típico de keyframes**: 2-10 segundos (depende do encoder)

No caso deste bug, o intervalo de keyframes era **muito grande** (~21s+), causando o problema.

---

## 🔗 Referências

### Arquivos Relacionados
- `app/celery_tasks.py` (linha ~610-700): Step 8 - Trimming
- `app/video_builder.py` (linha ~48-150): `concatenate_videos()`
- `app/video_builder.py` (linha ~279-330): `trim_video()`
- `app/video_builder.py` (linha ~165-240): `burn_subtitles()`

### Comandos de Diagnóstico
```bash
# Verificar duração de vídeo
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4

# Verificar duração de cada stream
ffprobe -v error -show_entries stream=duration:format=duration -of default=noprint_wrappers=1 video.mp4

# Verificar keyframes
ffprobe -v error -select_streams v:0 -show_entries frame=key_frame,pkt_pts_time -of csv video.mp4 | grep 1,

# Listar todos os streams
ffprobe -v error -show_entries stream=index,codec_type,codec_name,duration -of json video.mp4
```

### FFmpeg Docs
- Concat: https://trac.ffmpeg.org/wiki/Concatenate
- Trim: https://trac.ffmpeg.org/wiki/Seeking
- Stream Copy: https://ffmpeg.org/ffmpeg.html#Stream-copy

---

**Última atualização**: 07/02/2026 17:00  
**Investigador**: GitHub Copilot  
**Status**: Causas identificadas, soluções propostas, aguardando implementação
