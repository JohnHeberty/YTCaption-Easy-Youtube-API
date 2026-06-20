# Validação

## Regra Principal

Toda alteração deve ser validada quando possível.

Preferência de validação:
```
1. Teste específico do fluxo alterado
2. Type-check (python -m py_compile)
3. Lint (ruff)
4. Build (docker compose build)
5. Verificação manual descrita
```

## Todos os Serviços Python

```bash
cd /root/YTCaption-Easy-Youtube-API/services/se{N}-{name}

# Syntax check
python -m py_compile app/main.py

# Testes
python -m pytest tests/ -v

# Lint
python -m ruff check .

# Import check
python -c "from app.main import app"
```

## SE8 (Image Engine)

```bash
# Health check
curl http://localhost:8008/health

# Deep health
curl http://localhost:8008/health/deep

# Teste de geração
curl -X POST http://localhost:8008/v1/generate \
  -H "X-API-Key: se8-test-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"test","negative_prompt":"","styles":["Fooocus V2"],"performance_selection":"Speed","aspect_ratios_selection":"1024×1024","image_number":1}'
```

## SE9 (Video IMG)

```bash
# Health check
curl http://localhost:8009/ping

# Testes unitários (27/27)
cd /root/YTCaption-Easy-Youtube-API/services/se9-make-video-img
python -m pytest tests/ -v

# Verificar warnings (deve ser 0)
python -W error::DeprecationWarning -c "from app.main import app"
```

## SE11 (Clothes Removal)

```bash
# Health check
curl http://localhost:8011/health

# Deep health
curl http://localhost:8011/health/deep

# Testes
cd /root/YTCaption-Easy-Youtube-API/services/se11-clothes-removal
python -m pytest tests/ -v
```

## Shared Library

```bash
cd /root/YTCaption-Easy-Youtube-API/shared

# Verificar warnings Pydantic v2 (deve ser 0)
python -W error::DeprecationWarning -c "from shared.config_utils.base_settings import SettingsBase"
python -W error::DeprecationWarning -c "from shared.models.base import BaseJob"

# Testes
python -m pytest tests/ -v
```

## Se Não Puder Validar

Responder claramente:
```
Validação:
- Não executada.

Motivo:
- ...

Como validar manualmente:
- ...

Risco restante:
- ...
```

Nunca dizer "testado" sem teste real.

## Templates de Resposta Final

### Com arquivos alterados
```
Arquivos alterados:
- ...

O que mudou:
- ...

Como validei:
- ...

Observações/riscos:
- ...
```

### Sem arquivos alterados
```
Arquivos alterados:
- Nenhum.

O que foi feito:
- ...

Como validar:
- ...

Observações/riscos:
- ...
```

### Validação não executada
```
Validação:
- Não executada.

Motivo:
- ...

Como validar manualmente:
- ...

Risco restante:
- ...
```
