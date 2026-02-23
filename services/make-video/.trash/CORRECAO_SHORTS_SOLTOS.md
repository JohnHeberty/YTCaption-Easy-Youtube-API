# 🚨 CORREÇÃO: Shorts Soltos (Sem Amarração com Job)

## 📋 Problema Identificado

**Data**: 2026-02-16

Vídeos shorts estavam sendo salvos diretamente em `data/raw/shorts/{video_id}.mp4` **SEM amarração com job_id**, resultando em:

❌ **16 vídeos soltos** encontrados em `data/raw/shorts/`  
❌ Arquivos sem vínculo com jobs  
❌ Impossível saber qual job baixou qual short  
❌ Limpeza automática não funciona corretamente  

### Estrutura Anterior (ERRADA)
```
data/raw/shorts/
├── b4uve_BsdGA.mp4       ← SOLTO (não sabemos qual job)
├── tERpcdy8RVk.mp4       ← SOLTO
├── KE663qmFzO8.mp4       ← SOLTO
└── ... (16 arquivos)
```

---

## ✅ Solução Implementada

### Nova Estrutura (CORRETA)
```
data/raw/shorts/
├── {job_id_1}/           ← Pasta do job
│   ├── b4uve_BsdGA.mp4
│   ├── tERpcdy8RVk.mp4
│   └── KE663qmFzO8.mp4
├── {job_id_2}/
│   ├── p2oUOAB6q7c.mp4
│   └── bW1xgDiwG2w.mp4
└── {job_id_3}/
    └── h2pPvY6aSIY.mp4
```

✅ **Todos os shorts amarrados ao job_id**  
✅ **Fácil identificar origem dos arquivos**  
✅ **Limpeza automática por job funciona**  

---

## 🔧 Alterações no Código

### 1. celery_tasks.py (linha 340)

**ANTES**:
```python
output_path = Path(settings['shorts_cache_dir']) / f"{video_id}.mp4"
```

**DEPOIS**:
```python
# FIXED: Organizar shorts por job_id para evitar arquivos soltos
job_shorts_dir = Path(settings['shorts_cache_dir']) / job_id
job_shorts_dir.mkdir(parents=True, exist_ok=True)
output_path = job_shorts_dir / f"{video_id}.mp4"
```

### 2. celery_tasks.py (linha 1323 - validação)

**ANTES**:
```python
shorts_cache_dir = Path(settings['shorts_cache_dir'])
if not shorts_cache_dir.exists() or not list(shorts_cache_dir.glob("*.mp4")):
    return {"valid": False, "reason": "No shorts available in cache"}
```

**DEPOIS**:
```python
shorts_cache_dir = Path(settings['shorts_cache_dir'])
job_shorts_dir = shorts_cache_dir / job.job_id
if not job_shorts_dir.exists() or not list(job_shorts_dir.glob("*.mp4")):
    return {"valid": False, "reason": f"No shorts available for job {job.job_id}"}
```

### 3. download_shorts_stage.py (linha 214)

**ANTES**:
```python
output_path = Path(context.settings['shorts_cache_dir']) / f"{video_id}.mp4"
```

**DEPOIS**:
```python
# FIXED: Organizar shorts por job_id para evitar arquivos soltos
job_shorts_dir = Path(context.settings['shorts_cache_dir']) / context.job_id
job_shorts_dir.mkdir(parents=True, exist_ok=True)
output_path = job_shorts_dir / f"{video_id}.mp4"
```

---

## 🧹 Limpeza de Arquivos Antigos

### Script Criado: `cleanup_loose_shorts.sh`

**Uso**:
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
./cleanup_loose_shorts.sh
```

**Funcionalidades**:
- ✅ Lista todos os arquivos soltos (sem job_id)
- ✅ Mostra tamanho total a ser removido
- ✅ Pede confirmação antes de deletar
- ✅ Remove apenas arquivos soltos (preserva pastas com job_id)

### Limpeza Manual (Alternativa)

```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video/data/raw/shorts

# Listar arquivos soltos
find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \)

# Contar arquivos soltos
find . -maxdepth 1 -type f -name "*.mp4" | wc -l

# Ver tamanho total
find . -maxdepth 1 -type f -name "*.mp4" -exec du -ch {} + | grep total

# REMOVER (cuidado!)
find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) -delete
```

---

## ✅ Validação

### Verificar que NÃO há arquivos soltos:
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video/data/raw/shorts

# Deve retornar 0 (zero)
find . -maxdepth 1 -type f -name "*.mp4" | wc -l
```

### Verificar estrutura correta (com job_id):
```bash
# Listar pastas (jobs)
ls -la data/raw/shorts/

# Exemplo esperado:
# drwxr-xr-x  QiKYji3UtJ2NHTvBQPJQRa/
# drwxr-xr-x  QizVH9MjcPXgUaBXb3K854/
# drwxr-xr-x  fNjeXXCwX49YHhFeuDPpxH/

# Ver shorts de um job específico
ls -la data/raw/shorts/QiKYji3UtJ2NHTvBQPJQRa/
```

---

## 📊 Impacto

### Antes da Correção
- ❌ 16 vídeos soltos sem rastreamento
- ❌ ~200-500 MB de arquivos órfãos
- ❌ Cleanup automático não funciona
- ❌ Impossível auditoria de jobs

### Depois da Correção
- ✅ 0 vídeos soltos
- ✅ Todos os shorts amarrados a jobs
- ✅ Cleanup automático funcional
- ✅ Auditoria completa de downloads por job

---

## 🚀 Deploy da Correção

### Opção 1: Docker (Recomendado)
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Rebuild com código atualizado
./deploy_workaround.sh
```

### Opção 2: Manual
```bash
# As alterações já estão no código local
# Basta fazer rebuild dos containers:

docker compose down
docker rmi make-video-make-video make-video-make-video-celery make-video-make-video-celery-beat
docker compose build --no-cache
docker compose up -d
```

### Pós-Deploy: Limpar Arquivos Antigos
```bash
# Rodar script de limpeza
./cleanup_loose_shorts.sh
```

---

## 📝 Checklist de Validação

- [x] ✅ Código atualizado (celery_tasks.py)
- [x] ✅ Código atualizado (download_shorts_stage.py)
- [x] ✅ Script de limpeza criado
- [ ] ⏳ Docker rebuild
- [ ] ⏳ Executar limpeza de arquivos antigos
- [ ] ⏳ Testar novo job e validar estrutura

---

## 🎯 Comandos de Teste

### Criar novo job e validar estrutura:
```bash
# 1. Criar job
JOB_ID=$(curl -X POST http://localhost:8004/make-video \
  -F "audio_file=@audio.mp3" \
  -F "query=teste shorts organizados" \
  -F "max_shorts=10" | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 2. Aguardar download de shorts (alguns minutos)
watch "curl -s http://localhost:8004/jobs/$JOB_ID | jq '.status, .stages?.downloading_shorts'"

# 3. Validar estrutura de pastas
ls -la data/raw/shorts/$JOB_ID/

# 4. Verificar que NÃO há arquivos soltos
find data/raw/shorts/ -maxdepth 1 -type f -name "*.mp4"
# Resultado esperado: nenhuma saída (0 arquivos)
```

---

## 📚 Referências

- **Issue**: Vídeos shorts sem amarração com job_id
- **Arquivos Modificados**:
  - `app/infrastructure/celery_tasks.py` (2 locais)
  - `app/domain/stages/download_shorts_stage.py` (1 local)
- **Scripts Criados**:
  - `cleanup_loose_shorts.sh`
- **Documentos**:
  - Este arquivo (CORRECAO_SHORTS_SOLTOS.md)

---

**Status**: ✅ CORREÇÃO IMPLEMENTADA  
**Próximo Passo**: Rebuild Docker + Limpeza de arquivos antigos  
**Data**: 2026-02-16
