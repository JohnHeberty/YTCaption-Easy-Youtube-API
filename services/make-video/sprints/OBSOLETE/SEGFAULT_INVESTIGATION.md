# 🔬 INVESTIGAÇÃO: Segmentation Fault no Ensemble

**Data**: 2026-02-14 16:03 UTC  
**Status**: 🔴 **INVESTIGAÇÃO ATIVA**

---

## 📋 PROBLEMA

**Sintoma**: Segmentation fault ao combinar múltiplos detectores
**Impacto**: Impossível medir acurácia do ensemble completo (meta de 90%)

---

## 🧪 TESTES REALIZADOS

### Teste 1: CLIP Isolado
**Configuração**: Apenas CLIPClassifier  
**Resultado**: ✅ **FUNCIONA**  
**Acurácia**: 35.29%  
**Tempo**: 31.33s  
**Conclusão**: CLIP funciona perfeitamente sozinho

### Teste 2: Ensemble Completo (3 modelos)
**Configuração**: PaddleOCR + CLIP + EasyOCR (paralelo)  
**Resultado**: ❌ **SEGFAULT**  
**Erro**: `FatalError: Segmentation fault (SIGSEGV)`  
**Local**: Durante inicialização do EasyOCR após CLIP  
**Conclusão**: Não é possível usar 3 modelos juntos

### Teste 3: 2 Detectores (CLIP + EasyOCR)
**Configuração**: CLIP + EasyOCR (sem PaddleOCR)  
**Resultado**: ❌ **SEGFAULT**  
**Erro**: Mesmo erro durante EasyOCR init  
**Conclusão**: Problema não é específico do PaddleOCR

### Teste 4: Desabilitar Threading
**Configuração**: `OMP_NUM_THREADS=1` + CLIP + EasyOCR  
**Resultado**: ❌ **SEGFAULT**  
**Erro**: Mesmo erro  
**Conclusão**: Não é problema de threading

### Teste 5: Processamento Serializado
**Configuração**: Processar detectores um por vez (não paralelo)  
**Resultado**: ❌ **SEGFAULT**  
**Erro**: Mesmo erro ao iniciar EasyOCR após usar CLIP  
**Conclusão**: Não é problema de paralelização

### Teste 6: CLIP + PaddleOCR (EM ANDAMENTO)
**Configuração**: CLIP + PaddleOCR (sem EasyOCR)  
**Status**: ⏳ **EXECUTANDO...**  
**Objetivo**: Verificar se o problema é específico do EasyOCR  
**Expectativa**:
- Se **funcionar**: EasyOCR é o culpado
- Se **segfault**: Problema é qualquer combinação de múltiplos detectores

---

## 🔍 ANÁLISE DO PROBLEMA

### Padrão Identificado

```
1. CLIP carrega OK
2. CLIP processa vídeos OK
3. CLIP é deletado (del detector)
4. Segundo detector inicia carregamento
5. ❌ SEGFAULT durante init do segundo detector
```

### Hipóteses

#### Hipótese A: Conflito de Bibliotecas (PROVÁVEL)
**Evidência**:
- EasyOCR usa PaddlePaddle internamente
- CLIP usa PyTorch
- PaddleOCR usa PaddlePaddle
- Possível conflito PyTorch ↔ PaddlePaddle

**Teste**: Se CLIP + PaddleOCR funcionar, confirmamos que PyTorch + PaddlePaddle OK  
**Status**: ⏳ Teste 6 em andamento

#### Hipótese B: Memória Não Liberada (PROVÁVEL)
**Evidência**:
- `del detector` pode não liberar memória imediatamente
- CLIP pode deixar tensores CUDA ou CPU alocados
- Garbage collector não roda entre detectores

**Solução potencial**:
```python
import gc
del detector
gc.collect()  # Força garbage collection
torch.cuda.empty_cache()  # Se usar CUDA
time.sleep(1)  # Espera liberação
```

#### Hipótese C: Shared Libraries Conflitantes (MENOS PROVÁVEL)
**Evidência**:
- OpenCV usado por múltiplos detectores
- Versões diferentes de libav/ffmpeg
- Conflito de dlopen() em bibliotecas

**Teste**: Verificar ldd dos módulos importados

#### Hipótese D: AV1 Codec Issues (MENOS PROVÁVEL)
**Evidência**:
- Erros de AV1 buffer allocation observados nos logs
- Pode ser secundário, não a causa raiz

---

## 🛠️ SOLUÇÕES POSSÍVEIS

### Solução 1: Processos Separados ⭐ **RECOMENDADA**

**Descrição**: Cada detector roda em **processo separado** (não thread)

**Implementação**:
```python
from multiprocessing import Process, Queue

def run_detector_in_process(detector_class, video_path, queue):
    """Roda detector em processo isolado"""
    detector = detector_class()
    result = detector.detect(video_path)
    queue.put(result)

# Uso
queue = Queue()
process = Process(target=run_detector_in_process, args=(CLIPClassifier, video, queue))
process.start()
process.join()
result = queue.get()
```

**Vantagens**:
- ✅ Isolamento completo de memória
- ✅ Sem conflito de bibliotecas
- ✅ Alta probabilidade de sucesso (95%)

**Desvantagens**:
- ⚠️ Overhead de IPC (inter-process communication)
- ⚠️ Mais complexo de implementar
- ⚠️ Serialização de objetos necessária

**Tempo estimado**: 2-3 horas

---

### Solução 2: Forçar Garbage Collection

**Descrição**: Liberar memória explicitamente entre detectores

**Implementação**:
```python
import gc
import torch

detector = CLIPClassifier(device='cpu')
result = detector.detect(video)
del detector

# Forçar limpeza
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
time.sleep(2)  # Espera liberação

# Agora carregar próximo detector
```

**Vantagens**:
- ✅ Muito simples
- ✅ Rápido de implementar (15 min)

**Desvantagens**:
- ⚠️ Pode não resolver (60% sucesso)
- ⚠️ Delay de 2s entre detectores

**Tempo estimado**: 15 minutos

---

### Solução 3: Usar Apenas 2 Detectores Compatíveis

**Descrição**: Se Teste 6 funcionar, usar apenas CLIP + PaddleOCR

**Configuração**:
- CLIP: 1.2 peso
- PaddleOCR: 1.0 peso
- **Remover EasyOCR**

**Vantagens**:
- ✅ Funciona (se Teste 6 passar)
- ✅ Sem mudanças no código

**Desvantagens**:
- ❌ Acurácia pode cair (menos detectores)
- ❌ Meta de 90% pode não ser atingida

**Tempo estimado**: 0 horas (só remover EasyOCR)

---

### Solução 4: Containerização Isolada

**Descrição**: Cada detector em container Docker separado

**Implementação**:
```bash
docker run --rm clip-detector video.mp4 > result_clip.json
docker run --rm easyocr-detector video.mp4 > result_easy.json
docker run --rm paddle-detector video.mp4 > result_paddle.json
# Combinar resultados
```

**Vantagens**:
- ✅ Isolamento TOTAL
- ✅ 100% de sucesso garantido
- ✅ Escalável (Kubernetes, etc.)

**Desvantagens**:
- ❌ Muito lento (overhead de container)
- ❌ Complexo (requer Docker, orquestração)
- ❌ Overkill para o problema

**Tempo estimado**: 4-6 horas

---

## 📊 REQUISITOS PARA 90% ACCURACY

### Estimativa com 2 Detectores (CLIP + PaddleOCR)

**Baseline Individual**:
- CLIP: 35% (testado)
- PaddleOCR: ~70% (estimado)

**Ensemble de 2**:
```math
Ensemble = (CLIP + PaddleOCR) / 2
         ≈ (35% + 70%) / 2
         ≈ 52-65%
```

**Conclusão**: 2 detectores **NÃO SUFICIENTE** para 90%

### Estimativa com 3 Detectores (IDEAL)

**Baseline Individual**:
- CLIP: 35%
- PaddleOCR: 70%
- EasyOCR: 75%

**Ensemble de 3** (confidence-weighted):
```math
Ensemble ≈ 75-85% (weighted vote)
Ensemble ≈ 80-90% (com Sprint 07 features)
```

**Conclusão**: 3 detectores **NECESSÁRIO** para 90%

---

## 🎯 PRÓXIMOS PASSOS

### Passo 1: Aguardar Teste 6 (EM ANDAMENTO)
- ⏳ Testando CLIP + PaddleOCR sem EasyOCR
- Resultado esperado em ~5-10 minutos

### Passo 2: Decisão baseada no Teste 6

#### Se Teste 6 FUNCIONA ✅:
```
Conclusão: EasyOCR é o problema
Opções:
  A) Usar CLIP + PaddleOCR apenas (acurácia ~60-70%)
  B) Substituir EasyOCR por outro detector (Tesseract, Azure OCR)
  C) Implementar EasyOCR em processo separado
```

#### Se Teste 6 SEGFAULT ❌:
```
Conclusão: Qualquer combinação falha
Solução OBRIGATÓRIA:
  → Implementar Solução 1 (Processos Separados)
  → Garantir isolamento total de memória
```

### Passo 3: Implementar Solução Escolhida

**Prioridade 1**: Solução que FUNCIONE (mesmo que lenta)  
**Prioridade 2**: Medir acurácia real  
**Prioridade 3**: Otimizarapós comprovação

---

## ⏱️ TIMELINE

| Ação | Tempo | Status |
|------|-------|--------|
| Teste 6 completar | 5-10 min | ⏳ Em andamento |
| Análise resultado | 5 min | ⏳ Pendente |
| Implementar GC forçado | 15 min | ⏳ Pendente |
| Se falhar: Processos separados | 2-3h | ⏳ Pendente |
| Medir acurácia final | 10-30 min | ⏳ Pendente |
| **TOTAL** | **3-4h** | ⏳ |

**Meta**: Ter acurácia medida hoje, mesmo que solução não seja otimizada.

---

## 📝 NOTAS

1. **Prioridade absoluta**: Fazer FUNCIONAR
2. **Não otimizar prematuramente**: Primeiro funcione, depois otimize
3. **Meta de 90%**: Pode requerer 3 detectores ou ajuste de thresholds
4. **Fallback**: Se 90% impossível, documentar razão e próximos passos

---

**Última atu alização**: 2026-02-14 16:05 UTC  
**Responsável**: Ensemble Optimization System  
**Arquivo**: `sprints/SEGFAULT_INVESTIGATION.md`
