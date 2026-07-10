# Quickstart — SE11 Clothes Removal

**Tempo estimado:** 5 minutos

---

## 1. Setup

```bash
cd services/se11-clothes-removal

# Dependências
pip install -r requirements.txt

# Configurar .env
cp .env.example .env  # ou criar manualmente
```

`.env` mínimo:
```
APP_NAME=clothes-removal
REDIS_URL=redis://localhost:6379/11
API_KEY=se11-test-key-2026
SE10_URL=http://localhost:8010
SE8_URL=http://localhost:8008
```

---

## 2. Iniciar Serviços Upstream

```bash
# SE10 (clothes segmentation) — porta 8010
cd ../se10-clothes-segmentation && python run.py

# SE8 (image generation / inpainting) — porta 8008
cd ../se8-image-generation && python run.py
```

---

## 3. Iniciar SE11

```bash
cd services/se11-clothes-removal
python run.py
```

---

## 4. Primeiro Teste

```bash
# Health check
curl http://localhost:8011/health

# Deep health (verifica SE10 + SE8)
curl http://localhost:8011/health/deep

# Criar job clothes removal
curl -X POST "http://localhost:8011/jobs" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@imagem.png" \
  -F "mode=clothes"

# Poll status
curl "http://localhost:8011/jobs/cr_XXXXXX" \
  -H "X-API-Key: se11-test-key-2026"

# Download resultado
curl "http://localhost:8011/jobs/cr_XXXXXX/download" \
  -H "X-API-Key: se11-test-key-2026" \
  -o resultado.png
```

---

## 5. Modos de Uso

### Clothes (default) — Remove roupas específicas
```bash
curl -X POST "http://localhost:8011/jobs" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@foto.png" \
  -F "mode=clothes" \
  -F "classes=shirt,pants" \
  -F "detector=segformer"
```

### Person — Remove torso inteiro
```bash
curl -X POST "http://localhost:8011/jobs" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@foto.png" \
  -F "mode=person"
```

### NSFW — Pipeline produção (qualidade fixa)
```bash
curl -X POST "http://localhost:8011/jobs/nsfw" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@foto.png"
```

### NSFW Test — Pipeline experimental (parâmetros livres)
```bash
curl -X POST "http://localhost:8011/jobs/nsfw-test" \
  -H "X-API-Key: se11-test-key-2026" \
  -F "file=@foto.png" \
  -F "inpaint_strength=0.90" \
  -F "use_faceid=true" \
  -F "faceid_weight=0.85"
```

---

## 6. Endpoints Rápidos

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/deep` | Deep health (SE10 + SE8) |
| `GET` | `/ping` | Ping |
| `GET` | `/modes` | Modos disponíveis |
| `GET` | `/detectors` | Detectors disponíveis |
| `GET` | `/config` | Configuração atual |
| `POST` | `/jobs` | Criar job clothes/person |
| `POST` | `/jobs/nsfw` | Criar job NSFW produção |
| `POST` | `/jobs/nsfw-test` | Criar job NSFW teste |
| `GET` | `/jobs` | Listar jobs |
| `GET` | `/jobs/{id}` | Status do job |
| `DELETE` | `/jobs/{id}` | Deletar job |
| `GET` | `/jobs/{id}/download` | Download resultado |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Cleanup |

---

## 7. Troubleshooting

| Problema | Solução |
|----------|---------|
| `503 degraded` no `/health/deep` | Verificar se SE10 e SE8 estão rodando |
| `401 Invalid or missing API key` | Verificar header `X-API-Key` |
| Job stuck em `detecting` | SE10 pode estar lento — aumentar `SE10_TIMEOUT` |
| Job stuck em `inpainting` | SE8 pode estar lento — aumentar `SE8_TIMEOUT` |
| `413 Request Entity Too Large` | Aumentar `MAX_FILE_SIZE_MB` |
