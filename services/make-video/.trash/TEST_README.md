# 🧪 Scripts de Teste - Sistema de Rastreabilidade

Testes completos para validar o novo sistema de tracking, cleanup e file movement.

## 📋 Scripts Disponíveis

### 1. **test_quick.sh** ⚡ (RECOMENDADO PARA INÍCIO)
```bash
bash test_quick.sh
```

**O que testa:**
- ✅ VideoStatusStore (3 tabelas: approved, rejected, error)
- ✅ FileOperations (move files entre stages)
- ✅ Estrutura de diretórios
- ✅ Banco de dados SQLite
- ✅ Prevenção de retry

**Vantagem**: Não requer container rodando, testa funcionalidade core.

**Duração**: ~5 segundos

---

### 2. **test_api_curl.sh** 🌐 (REQUER CONTAINER)
```bash
# 1. Subir container primeiro
cd /root/YTCaption-Easy-Youtube-API/services/make-video
docker compose up -d

# 2. Aguardar 15 segundos

# 3. Executar teste
bash test_api_curl.sh
```

**O que testa:**
- ✅ GET / (documentação)
- ✅ GET /health
- ✅ GET /docs (Swagger)
- ✅ POST /download (pipeline com 3 vídeos)
- ✅ GET /jobs/{id} (monitoramento)

**Duração**: ~30 segundos (+ tempo de processamento)

---

### 3. **test_system_complete.sh** 🎯 (TESTE COMPLETO)
```bash
bash test_system_complete.sh
```

**O que testa:**
- Tudo do `test_quick.sh`
- Tudo do `test_api_curl.sh`
- + Verificação de arquivos orphan
- + Stats detalhados
- + Cleanup service (se disponível)
- + Pipeline com 5 vídeos

**Duração**: ~3-5 minutos

---

## 🚀 Execução Rápida

### Teste Core (sem container):
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
bash test_quick.sh
```

### Teste API (com container):
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
docker compose up -d && sleep 15
bash test_api_curl.sh
```

---

## ✅ Resultados Esperados

### **test_quick.sh**
```
✅ VideoStatusStore: FUNCIONANDO PERFEITAMENTE
   - 3 tabelas criadas (approved, rejected, error)
   - Métodos add/get/list: OK
   - Prevenção de retry: OK

✅ FileOperations: FUNCIONANDO PERFEITAMENTE
   - Move raw/ → transform/: OK
   - Move transform/ → approved/: OK
   - Validação: Arquivo antigo removido

✅ Banco de dados: data/database/video_status.db (44K)
✅ Estrutura de diretórios: OK
```

### **test_api_curl.sh**
```
✅ Serviço respondendo em http://localhost:8004
✅ GET  /              - Status: 200
✅ GET  /health        - Status: 200 (ou 503 se inicializando)
✅ GET  /docs          - Status: 200
✅ POST /download      - Job criado: {job_id}
✅ GET  /jobs/{id}     - Status: processing/completed
```

---

## 🔍 Debug

### Container não está rodando?
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
docker compose logs make-video --tail 50
```

### Erro no banco de dados?
```bash
sqlite3 data/database/video_status.db "SELECT name FROM sqlite_master WHERE type='table';"
```

### Ver últimos erros catalogados?
```bash
python3 -c "
import sys
sys.path.insert(0, '/root/YTCaption-Easy-Youtube-API/services/make-video')
from app.services.video_status_factory import get_video_status_store
store = get_video_status_store()
for err in store.list_errors(limit=5):
    print(f'{err[\"video_id\"]}: {err[\"error_type\"]} ({err[\"stage\"]})')
"
```

---

## 📊 Arquivos de Saída

Os testes NÃO criam arquivos de log por padrão. Output vai para stdout.

Para salvar output:
```bash
bash test_quick.sh > test_results.txt 2>&1
bash test_api_curl.sh > api_test_results.txt 2>&1
```

---

## 🎯 Próximos Passos

Após os testes passarem:

1. **Integrar no pipeline** (ver [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md))
2. **Rebuild container** com as mudanças:
   ```bash
   docker compose build make-video --no-cache
   docker compose up -d
   ```
3. **Testar com volume real** (50+ vídeos)
4. **Monitorar CleanupService** (a cada 10 min)

---

## 📖 Documentação

- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Como integrar no código
- **[README.md](README.md)** - Documentação geral do serviço
- **/docs/** - Swagger UI (quando container estiver rodando)

---

## 🐛 Troubleshooting

| Problema | Solução |
|----------|---------|
| `curl: (7) Failed to connect` | Container não está rodando → `docker compose up -d` |
| `ModuleNotFoundError` | Path incorreto → Execute do dir `/services/make-video/` |
| `sqlite3.OperationalError` | Banco corrompido → Delete e recrie: `rm data/database/video_status.db` |
| `FileNotFoundError` | Diretórios não existem → Script cria automaticamente |
| Pipeline timeout | Aumente max_shorts para 3-5 vídeos apenas nos testes |

---

## ✨ Comandos Úteis

```bash
# Ver estado atual do banco
sqlite3 data/database/video_status.db "
SELECT 'Approved' as type, COUNT(*) FROM approved_videos
UNION ALL SELECT 'Rejected', COUNT(*) FROM rejected_videos
UNION ALL SELECT 'Errors', COUNT(*) FROM error_videos;
"

# Limpar banco para novo teste
sqlite3 data/database/video_status.db "
DELETE FROM approved_videos WHERE metadata LIKE '%test%';
DELETE FROM rejected_videos WHERE metadata LIKE '%test%';
DELETE FROM error_videos WHERE metadata LIKE '%test%';
"

# Stats do sistema
python3 -c "
import sys; sys.path.insert(0, '.')
from app.services.video_status_factory import get_video_status_store
print(get_video_status_store().get_stats())
"
```
