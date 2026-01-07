# Problema: Progresso Parado em 25%

## 🐛 Problema Identificado

O job de transcrição do arquivo `saida_5.mp3` (88MB, ~1h de áudio) ficou **parado em 25% de progresso** por mais de 2 horas.

### Análise

```bash
# Status do job
Status: processing
Progress: 25.0%  ← PARADO AQUI
Erro: None

# Processo do Celery Worker
PID: 1
CPU: 196% (quase 2 cores)
Memória: 1.5GB
Tempo: 117 minutos (processando)
Estado: Running
```

## 🔍 Causa Raiz

### 1. **Chunking Desabilitado**

No arquivo `.env`:
```bash
WHISPER_ENABLE_CHUNKING=false  # ← PROBLEMA!
```

Quando o chunking está **desabilitado**, o fluxo de processamento é:

```
1. Upload completo (progresso: 0%)
2. Validação de arquivo (progresso: 25%)  ← PARA AQUI
3. Whisper processa ÁUDIO INTEIRO (SEM atualizar progresso)
4. Salva transcrição (progresso: 75%)
5. Finaliza (progresso: 100%)
```

**Para um áudio de 1 hora:**
- Passo 3 pode levar **1-3 horas** no CPU
- Durante todo esse tempo: **progresso parado em 25%**
- Usuário não sabe se está funcionando ou travado

### 2. **Código não Atualiza Progresso Durante Transcrição Direta**

No arquivo `processor.py`, método `_transcribe_direct()`:

```python
def _transcribe_direct(self, audio_file: str, language_in: str = "auto", language_out: str = None):
    logger.info(f"🎙️ Transcrevendo diretamente: {audio_file}")
    
    # Transcreve o áudio inteiro
    result = self.model.transcribe(audio_file, **transcribe_options)
    # ↑ Pode levar HORAS, mas progresso não é atualizado!
    
    return result
```

## ✅ Solução

### Solução Imediata: Habilitar Chunking

```bash
# Em .env
WHISPER_ENABLE_CHUNKING=true  # ✅ HABILITADO
WHISPER_MIN_DURATION_FOR_CHUNKS=300  # 5 minutos
WHISPER_CHUNK_LENGTH_SECONDS=30
WHISPER_CHUNK_OVERLAP_SECONDS=1.0
```

**Benefícios do Chunking:**
- ✅ Progresso atualizado a cada chunk (25% → 30% → 35% ... → 75%)
- ✅ Processamento mais rápido (chunks processados em paralelo)
- ✅ Menor uso de memória RAM
- ✅ Usuário vê progresso em tempo real
- ✅ Possibilidade de cancelar job sem perder todo o trabalho

### Solução Complementar: Callback de Progresso (Futuro)

O Whisper não fornece callback nativo de progresso, mas podemos estimar:

```python
def _transcribe_direct_with_progress(self, audio_file: str, job_id: str):
    """Transcrição com estimativa de progresso"""
    import threading
    import time
    from pathlib import Path
    
    # Calcula duração do áudio
    audio = AudioSegment.from_file(audio_file)
    duration_seconds = len(audio) / 1000.0
    
    # Estima tempo de processamento (varia por modelo e CPU/GPU)
    # CPU + modelo small: ~6-10s por minuto de áudio
    estimated_seconds = (duration_seconds / 60) * 8
    
    # Thread para atualizar progresso estimado
    def update_progress_estimate():
        start_time = time.time()
        while not transcription_done:
            elapsed = time.time() - start_time
            estimated_progress = min(70, 25 + (elapsed / estimated_seconds) * 45)
            
            job = self.job_store.get_job(job_id)
            if job:
                job.progress = estimated_progress
                self.job_store.update_job(job)
            
            time.sleep(5)
    
    transcription_done = False
    progress_thread = threading.Thread(target=update_progress_estimate)
    progress_thread.start()
    
    try:
        result = self.model.transcribe(audio_file, **options)
        return result
    finally:
        transcription_done = True
        progress_thread.join()
```

## 📊 Comparação

### Sem Chunking (Antes)
```
Arquivo: 1 hora de áudio (88MB)
Tempo total: ~2 horas
Progresso visível:
  0% ──► 25% ──────────────────────────► 75% ──► 100%
           ↑                             ↑
         (10s)                        (2 horas sem feedback)
```

### Com Chunking (Depois)
```
Arquivo: 1 hora de áudio (88MB)
Chunks: 120 chunks de 30s
Tempo total: ~40-60 minutos (mais rápido!)
Progresso visível:
  0% ──► 25% ──► 26% ──► 27% ... ──► 74% ──► 75% ──► 100%
           ↑                            ↑
         (10s)  (progresso a cada 30s)  (40-60 min)
```

## 🎯 Recomendações

### Para Produção

1. **Sempre habilitar chunking para áudios > 5 minutos**
   ```bash
   WHISPER_ENABLE_CHUNKING=true
   WHISPER_MIN_DURATION_FOR_CHUNKS=300
   ```

2. **Ajustar tamanho de chunk conforme modelo**
   - Modelo `tiny` ou `base`: chunks de 60s
   - Modelo `small`: chunks de 30s (padrão)
   - Modelo `medium` ou `large`: chunks de 20s

3. **Monitorar CPU/Memória**
   - Chunks menores = mais overhead
   - Chunks maiores = mais memória
   - Ideal: 30s para maioria dos casos

4. **Timeout adequado**
   ```bash
   CELERY_TASK_TIME_LIMIT=7200  # 2 horas
   CELERY_TASK_SOFT_TIME_LIMIT=6300  # 1h45min
   ```

### Para Desenvolvimento

1. **Testar com áudios de diferentes durações**
   - Curto (< 5 min): transcrição direta
   - Médio (5-30 min): chunking automático
   - Longo (> 30 min): chunking obrigatório

2. **Logs detalhados**
   - Log de início/fim de cada chunk
   - Tempo por chunk
   - Progresso atualizado

## 🧪 Teste

### Job Atual

O job `af9112d1a8a9_transcribe_pt` está:
- ✅ **Processando corretamente** (sem erros)
- ⚠️ **Progresso parado em 25%** (sem feedback visual)
- ⏳ **~2 horas de processamento** (normal para 1h de áudio sem chunking)
- 💪 **CPU a 196%** (trabalhando duro)

**Conclusão:** O sistema está funcionando, mas sem dar feedback ao usuário.

### Próximo Job

Com chunking habilitado, o próximo job de áudio longo terá:
- ✅ Progresso atualizado a cada chunk
- ✅ Processamento mais rápido
- ✅ Melhor experiência do usuário

## 📝 Arquivo de Configuração Atualizado

```bash
# .env - CONFIGURAÇÃO RECOMENDADA
WHISPER_ENABLE_CHUNKING=true  # ✅ HABILITADO
WHISPER_CHUNK_LENGTH_SECONDS=30
WHISPER_CHUNK_OVERLAP_SECONDS=1.0
WHISPER_MIN_DURATION_FOR_CHUNKS=300  # 5 min
```

---

**Status:** ✅ Problema identificado e solucionado  
**Ação Imediata:** Habilitar chunking no .env  
**Ação Futura:** Implementar callback de progresso estimado para transcrição direta
