# OPTIMIZE - Oportunidades de Otimização

> **Última atualização:** Auto-gerado  
> **Escopo:** services/make-video  
> **Exclusões:** Zabbix, Grafana (conforme solicitado)

---

## 📊 Resumo Executivo

| Categoria | Impacto | Esforço | Prioridade |
|-----------|---------|---------|------------|
| OCR/EasyOCR | Alto | Médio | P0 |
| Memória/CPU | Alto | Baixo | P0 |
| Calibração | Alto | Baixo | P1 |
| Pipeline TRSD | Médio | Alto | P2 |
| Paralelização | Médio | Médio | P2 |
| Cache/Storage | Baixo | Baixo | P3 |

---

## P0 - Crítico

### 1. EasyOCR GPU Acceleration

**Arquivo:** `app/ocr_detector.py`, `app/video_validator.py`

**Situação atual:**
```python
self.ocr_reader = easyocr.Reader(['pt', 'en'], gpu=False, verbose=False)
```

**Problema:** OCR está rodando apenas em CPU, perdendo aceleração significativa.

**Otimização proposta:**
```python
import torch

def create_ocr_reader():
    gpu_available = torch.cuda.is_available()
    return easyocr.Reader(
        ['pt', 'en'], 
        gpu=gpu_available,  # Usar GPU quando disponível
        verbose=False
    )
```

**Impacto esperado:** 3-5x mais rápido com GPU NVIDIA

---

### 2. Limit de Frames por Vídeo

**Arquivo:** `app/video_validator.py`

**Situação atual:**
```python
def __init__(self, min_confidence: float = 0.40, frames_per_second: int = 6, max_frames: int = 240):
```

**Problema:** 240 frames máximos pode causar OOM em vídeos longos.

**Otimização implementada (verificar):**
```python
# Em calibrate_trsd_optuna.py já limitamos a 10 frames
# Considerar reduzir também em produção
max_frames: int = 30  # Suficiente para detectar legendas
```

**Impacto:** Redução de 8x no uso de memória em vídeos longos

---

### 3. Threshold de Confiança Calibrado

**Arquivo:** `app/config.py`, `.env`

**Situação atual:**
```python
ocr_confidence_threshold = 0.40  # Valor padrão
```

**Otimização:**
Após executar calibração Optuna, atualizar para valor otimizado:
```bash
# Verificar resultado da calibração
cat storage/calibration/optuna_incremental_results.json

# Atualizar .env com melhor threshold
OCR_CONFIDENCE_THRESHOLD=0.XX  # Usar best_threshold do Optuna
```

**Impacto:** Melhora significativa na acurácia (precisão vs recall)

---

## P1 - Alta Prioridade

### 4. Singleton Pattern para EasyOCR Reader

**Arquivo:** `app/ocr_detector.py`

**Situação atual:** Já implementado em `calibrate_trsd_optuna.py`

**Verificar implementação em produção:**
```python
# ✅ BOM - Singleton
_global_detector = None

def get_detector():
    global _global_detector
    if _global_detector is None:
        _global_detector = OCRDetector()
    return _global_detector

# ❌ RUIM - Instância por chamada
detector = OCRDetector()  # Cada chamada carrega modelo na memória!
```

**Ação:** Verificar se `celery_tasks.py` usa singleton ou cria múltiplas instâncias.

---

### 5. Garbage Collection Agressivo

**Arquivo:** `calibrate_trsd_optuna.py` (já implementado)

**Padrão recomendado para produção:**
```python
import gc

def process_video(video_path):
    result = detector.detect(video_path)
    
    # Liberar memória após cada vídeo
    if hasattr(gc, 'collect'):
        gc.collect()
    
    return result
```

**Arquivos para aplicar:**
- `app/celery_tasks.py` - Após cada job
- `app/video_validator.py` - Após validar cada vídeo

---

### 6. Conversão AV1→H.264 em Produção

**Arquivo:** `app/video_validator.py`

**Problema:** Vídeos AV1 são extremamente lentos para processar com EasyOCR.

**Pipeline atual (calibração):**
```python
def ensure_h264_videos(video_paths, temp_dir):
    # Detecta codec e converte se necessário
    codec = get_video_codec(video_path)
    if codec in ['av1', 'av01']:
        convert_to_h264(video_path, temp_path)
```

**Ação:** Considerar adicionar mesma lógica em `video_validator.py` quando detectar AV1.

---

## P2 - Média Prioridade

### 7. Processamento Paralelo de Frames

**Arquivo:** `app/video_validator.py`

**Situação atual:** Frames são processados sequencialmente.

**Otimização proposta:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def detect_subtitles_parallel(self, video_path: str, max_workers: int = 4):
    timestamps = self._get_sample_timestamps(duration)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(self._analyze_frame, video_path, ts): ts 
            for ts in timestamps
        }
        
        results = []
        for future in as_completed(futures):
            results.append(future.result())
    
    return self._aggregate_results(results)
```

**Impacto:** ~3x mais rápido em máquinas multi-core

**Cuidado:** EasyOCR não é thread-safe por padrão, usar lock se necessário.

---

### 8. Cache de Resultados de Validação

**Arquivo:** `app/video_validator.py`

**Proposta:**
```python
import hashlib
from functools import lru_cache

def _get_video_hash(self, video_path: str) -> str:
    """Hash do arquivo para cache"""
    with open(video_path, 'rb') as f:
        return hashlib.md5(f.read(1024*1024)).hexdigest()  # Primeiros 1MB

@lru_cache(maxsize=1000)
def has_subtitles_cached(self, video_hash: str) -> Tuple[bool, float]:
    """Retorna resultado em cache se disponível"""
    pass
```

**Impacto:** Evita reprocessar vídeos já validados

---

### 9. Dicionário de Palavras Expandido

**Arquivo:** `app/ocr_detector.py`

**Situação atual:**
```python
COMMON_WORDS_PT = {'que', 'para', 'com', ...}  # ~60 palavras
COMMON_WORDS_EN = {'the', 'and', 'you', ...}  # ~60 palavras
```

**Otimização:**
```python
# Carregar dicionário externo mais completo
def load_dictionary(lang: str) -> set:
    dict_path = Path(f'data/dictionaries/{lang}.txt')
    if dict_path.exists():
        return set(dict_path.read_text().splitlines())
    return DEFAULT_WORDS[lang]

COMMON_WORDS_PT = load_dictionary('pt')  # 1000+ palavras
COMMON_WORDS_EN = load_dictionary('en')  # 1000+ palavras
```

**Impacto:** Melhor recall na detecção de legendas válidas

---

### 10. Batch Processing com Celery

**Arquivo:** `app/celery_tasks.py`

**Situação atual:** Um job processa um vídeo por vez.

**Otimização:**
```python
@celery_app.task
def process_video_batch(video_ids: List[str]):
    """Agrupa múltiplos vídeos em um batch para otimizar uso de recursos"""
    detector = get_detector()  # Singleton
    
    results = []
    for video_id in video_ids:
        result = process_single_video(detector, video_id)
        results.append(result)
    
    return results
```

**Impacto:** Reduz overhead de inicialização do EasyOCR

---

## P3 - Baixa Prioridade

### 11. Compressão de Artefatos de Debug

**Arquivo:** `app/telemetry.py`

**Proposta:**
```python
import gzip

def save_artifact(self, data: bytes, filename: str):
    with gzip.open(f'{filename}.gz', 'wb') as f:
        f.write(data)
```

**Impacto:** ~80% menos espaço em disco para debug

---

### 12. Logs Estruturados com JSON

**Arquivo:** `app/file_logger.py`

**Situação atual:** Logs em formato texto.

**Otimização:**
```python
import json

def log_structured(self, level: str, message: str, **kwargs):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        **kwargs
    }
    self._write_log(json.dumps(log_entry))
```

**Impacto:** Facilita análise e alertas automatizados

---

### 13. Healthcheck mais Robusto

**Arquivo:** `docker-compose.yml`

**Situação atual:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
```

**Otimização:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; r=requests.get('http://localhost:8002/health'); exit(0 if r.json().get('status')=='healthy' else 1)"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s  # Tempo para carregar EasyOCR
```

---

## 🔬 Métricas de Calibração Atual

```bash
# Verificar status atual
cat storage/calibration/optuna_incremental_results.json
```

| Métrica | Valor Atual | Alvo |
|---------|-------------|------|
| Trials | 3 | 100 |
| Best Accuracy | 19.44% | 90%+ |
| Best Threshold | 0.55 | TBD |

**Próximos passos:**
1. Executar calibração completa (100 trials)
2. Aplicar best_threshold em produção
3. Re-testar com dataset de validação

---

## 📋 Checklist de Implementação

- [ ] Habilitar GPU no EasyOCR quando disponível
- [ ] Reduzir max_frames para 30 em produção
- [ ] Aplicar threshold otimizado do Optuna
- [ ] Verificar singleton em celery_tasks.py
- [ ] Adicionar GC após cada job
- [ ] Considerar conversão AV1→H.264 em produção
- [ ] Expandir dicionários PT/EN
- [ ] Implementar cache de validação
- [ ] Adicionar start_period no healthcheck

---

## 📚 Referências

- [EasyOCR GPU Support](https://github.com/JaidedAI/EasyOCR#gpu-support)
- [Optuna TPE Sampler](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html#tips-and-best-practices)
