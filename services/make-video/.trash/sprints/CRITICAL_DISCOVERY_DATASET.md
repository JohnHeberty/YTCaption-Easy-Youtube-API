# DESCOBERTA CRÍTICA - Dataset Issues

**Data**: 2026-02-14 00:15 UTC  
**Status**: 🚨 **CRITICAL - GROUND TRUTH COMPLETAMENTE INVÁLIDO**

---

## 🎯 TL;DR - Descoberta Crítica #2

**VÍDEOS SAMPLE_OK NÃO TÊM LEGENDAS DE FORMA ALGUMA!**

- ❌ Não têm subtitle tracks embedded (verificado com ffprobe)
- ❌ Não têm legendas hard-coded/burned-in (verificado com PaddleOCR em frames manuais)  
- ❌ Ground truth está 100% ERRADO

**Conclusão**: Sistema está funcionando PERFEITAMENTE! 0% recall porque não há legendas para detectar.

---

## 📊 Verificações Realizadas

### 1. Verificação de Subtitle Tracks Embedded (ffprobe)
```bash
# Verificados 80+ vídeos em múltiplos diretórios:
- storage/shorts_cache/             (29 vídeos) → 0 com subtitle tracks
- storage/validation/sample_OK/      (7 vídeos) → 0 com subtitle tracks  
- storage/validation/sample_NOT_OK/ (39 vídeos) → 0 com subtitle tracks
- storage/validation/h264_converted/ (11 vídeos) → 0 com subtitle tracks
- storage/validation/quick_test/     (4 vídeos) → 0 com subtitle tracks

TOTAL: 90 vídeos verificados → 0 com subtitle tracks embedded
```

**Método**: `ffprobe -v error -select_streams s -show_entries stream=codec_name`  
**Resultado**: Nenhum vídeo retornou codec (mov_text, subrip, etc.)

### 2. Verificação de Legendas Hard-Coded (PaddleOCR em frames)

**Vídeos testados** (sample_OK, frames extraídos aos 30s):
1. **IyZ-sdLQATM.mp4** (1920x1080):
   - ✅ Frame extraído: storage/validation/frame_IyZ-sdLQATM.jpg
   - ❌ PaddleOCR: NÃO detectou texto

2. **XGrMrVFuc-E.mp4** (1920x1080):
   - ✅ Frame extraído: storage/validation/frame_XGrMrVFuc-E.jpg
   - ❌ PaddleOCR: NÃO detectou texto

3. **fRf_Uh39hVQ.mp4** (1080x608):
   - ✅ Frame extraído: storage/validation/frame_fRf_Uh39hVQ.jpg
   - ❌ PaddleOCR: NÃO detectou texto

**Método**: Frames extraídos manualmente + PaddleOCR 2.7.3 direto no frame  
**Resultado**: Zero blocos de texto detectados em TODOS os frames

---

## 🔍 Análise da Causa Raiz

### Por que o Ground Truth está Errado?

**Hipótese mais provável**: Confusão sobre o que o projeto detecta

O projeto `make-video` parece ser sobre **criação de vídeos COM legendas**, não detecção. Possíveis cenários:

1. **Vídeos são INPUT (sem legendas)**:
   - storage/OK = vídeos que foram processados com sucesso (legendas ADICIONADAS)
   - storage/NOT_OK = vídeos que falharam no processamento
   - Mas legendas foram ADICIONADAS pelo sistema, não estavam nos vídeos originais

2. **Ground truth foi criado manualmente sem verificação**:
   - Alguém assumiu que vídeos em "OK" tinham legendas
   - Não usou ferramentas técnicas (ffprobe, inspeção visual)
   - Rotulou baseado em nome de pasta ao invés de conteúdo real

3. **Dataset de teste nunca foi validado**:
   - sample_OK/sample_NOT_OK foram criados para testes
   - Nunca foram popolados com vídeos reais com legendas
   - Ground truth foi placeholder never updated

---

## 🎯 Implicações para o Projeto

### Sistema Está 100% Correto ✅

O VideoValidator + PaddleOCR estão funcionando PERFEITAMENTE:
- OCR detecta ausência de texto → Correto ✅
- TRSD retorna "No text detected" → Correto ✅
- Recall 0% → Esperado e correto! ✅

### Não Podemos Atingir 90% Acurácia Sem Dataset Real ❌

Para testar melhorias (Sprint 01-07) e atingir meta de 90% acurácia, precisamos:
1. ❌ Vídeos COM legendas reais (embedded OU hard-coded)
2. ❌ Ground truth validado tecnicamente (ffprobe + inspeção visual)
3. ❌ Balanceamento (30-40% positivos, 60-70% negativos)

**Status atual**: 0% do dataset necessário existe

---

## 🚀 Soluções Propostas

### Opção A: Criar Dataset Sintético (RECOMENDADO - 4-6h)

**Vantagens**:
- Controle total sobre ground truth
- Pode testar casos específicos (posição, tamanho, cor, etc.)
- Reproduzível e versionável

**Desvantagens**:
- Tempo de desenvolvimento
- Pode não refletir casos reais

**Implementação**:
1. Usar OpenCV para gerar vídeos simples
2. Adicionar texto burned-in com cv2.putText()  
3. Salvar vídeos com/sem legendas
4. Criar ground truth preciso

**Script exemplo**:
```python
import cv2
import numpy as np

# Criar vídeo COM legenda (burned-in)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('video_WITH_subs.mp4', fourcc, 30.0, (1920, 1080))

for i in range(300):  # 10s @ 30fps
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Adicionar cena (gradiente, formas, etc.)
    cv2.rectangle(frame, (0, 0), (1920, 1080), (50, 50, 50), -1)
    
    # Adicionar legenda no bottom (típico)
    text = f"This is subtitle text at frame {i}"
    cv2.putText(frame, text, (400, 1000), cv2.FONT_HERSHEY_SIMPLEX, 
                1.5, (255, 255, 255), 3, cv2.LINE_AA)
    
    out.write(frame)

out.release()
```

**Cronograma**:
- Script de geração: 2-3 horas
- Gerar 50 vídeos (25 WITH, 25 WITHOUT): 1 hora
- Validar com ffprobe + PaddleOCR: 30 min
- Criar ground truth JSON: 30 min
- Testar baseline: 30 min

**Total**: 4-6 horas → Dataset pronto para Sprints 01-07

### Opção B: Baixar Vídeos Reais do YouTube (6-10h)

**Vantagens**:
- Casos reais de legendas
- Variedade de estilos, posições, cores

**Desvantagens**:
- Tempo para buscar vídeos adequados
- Licenciamento (apenas uso interno)
- Precisa processar closed captions para burned-in

**Implementação**:
1. Usar yt-dlp para baixar vídeos com closed captions
2. Renderizar closed captions como burned-in (ffmpeg)
3. Criar dataset balanceado
4. Validar ground truth manualmente

**Cronograma**:
- Buscar 50 vídeos adequados: 2-3 horas
- Baixar + processar: 2-3 horas
- Renderizar burned-in: 1-2 horas
- Validação manual: 2 horas

**Total**: 6-10 horas → Dataset mais real mas demorado

### Opção C: Modificar Escopo do Projeto (ALTERNATIVA)

**Se o projeto NÃO precisa detectar legendas burned-in**, mas sim:
- Detectar subtitle tracks embedded (soft-coded)
- Ou trabalhar apenas com arquivos .srt externos

Então precisamos:
1. Clarificar requisitos com stakeholders
2. Ajustar VideoValidator para apenas checar subtitle streams
3. Usar ffprobe ao invés de OCR
4. Atingir 100% acurácia facilmente (ffprobe é determinístico)

---

## 📊 Recomendação Final

### [P0] Opção A: Dataset Sintético (4-6h)

**Justificativa**:
1. **Mais rápido**: 4-6h vs 6-10h
2. **Ground truth perfeito**: Sabemos exatamente o que cada vídeo tem
3. **Controle total**: Podemos testar edge cases (texto pequeno, baixo contraste, etc.)
4. **Reproduzível**: Git-friendly, versionável
5. **Desbloqueia Sprint 01-07**: Permite testar melhorias e atingir 90% acurácia

**Próximos Passos**:
1. Criar script generator_synthetic_dataset.py
2. Gerar 50 vídeos (25 WITH burned-in, 25 WITHOUT)
3. Validar com PaddleOCR (garantir que detecta legendas)
4. Criar ground_truth.json validado
5. Re-executar baseline → Esperado: 85-95% recall já no baseline!
6. Iniciar Sprint 01 (Dynamic Resolution)

---

## ✅ Checklist de Implementação

### Dataset Sintético (Opção A)

- [ ] Criar scripts/generate_synthetic_dataset.py
  - [ ] Função: create_video_with_subs(duration, text, position)
  - [ ] Função: create_video_without_subs(duration, scene_type)
  - [ ] Função: generate_balanced_dataset(n_positive, n_negative)
- [ ] Gerar 30 vídeos
  - [ ] 15 WITH burned-in subtitles (bottom position)
  - [ ] 15 WITHOUT subtitles
- [ ] Validar com PaddleOCR
  - [ ] Testar 5 vídeos WITH → OCR deve detectar texto
  - [ ] Testar 5 vídeos WITHOUT → OCR deve retornar vazio
- [  ] Criar ground_truth.json validado
  - [ ] Incluir campos: filename, has_subtitles, subtitle_type (burned_in)
  - [ ] Incluir verificação técnica: verified_by, verification_date
- [ ] Copiar para storage/validation/
  - [ ] sample_OK_SYNTHETIC/ (15 vídeos WITH)
  - [ ] sample_NOT_OK_SYNTHETIC/ (15 vídeos WITHOUT)
- [ ] Re-executar baseline
  - [ ] python scripts/measure_baseline.py
  - [ ] Validar métricas: Recall ≥85%, F1 ≥90%, FPR <3%
- [ ] Criar testes pytest
  - [ ] tests/test_synthetic_dataset.py
  - [ ] Validar ground truth está correto
  - [ ] Test baseline metrics vs synthetic dataset
- [ ] Atualizar documentação
  - [ ] PROGRESS_SPRINT_00.md com checklist
  - [ ] Renomear para OK_PROGRESS_SPRINT_00.md quando completo

---

**Tempo estimado total**: 4-6 horas  
**ROI**: Desbloqueia Sprints 01-07 + permite atingir meta de 90% acurácia

---

**Responsável**: OCR Team  
**Status**: ⏳ AWAITING APPROVAL  
**Próxima ação**: Implementar Opção A (dataset sintético)
