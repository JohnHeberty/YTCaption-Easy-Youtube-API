# Comandos por Subprojeto

Todos os comandos devem rodar dentro do subprojeto correto. Nunca assumir comando na raiz do monorepo.

## Todos os Serviços Python (SE1-SE11)

```bash
cd /root/YTCaption-Easy-Youtube-API/services/se{N}-{name}

# Instalar dependências
pip install -r requirements.txt

# Rodar testes
python -m pytest tests/ -v

# Verificar syntax
python -m py_compile app/main.py

# Lint (se configurado)
python -m ruff check .
```

## SE1-SE6 (Celery Workers)

```bash
# API server
python -m app.main

# Celery worker
celery -A app.celery_app worker --loglevel=info

# Docker
docker compose up -d ytcaption-se{N}-{name}
```

## SE7 (Audio Generation - GPU)

```bash
# Rebuild
docker compose build ytcaption-se7-audio-generation
docker compose up -d ytcaption-se7-audio-generation

# Logs
docker logs ytcaption-se7-audio-generation -f

# Health
curl http://localhost:8007/ping
```

## SE8 (Image Engine - GPU)

```bash
# Rebuild
docker compose build image-engine
docker compose up -d image-engine

# Logs
docker logs image-engine -f

# Health
curl http://localhost:8008/ping

# Clean VRAM
curl -X POST http://localhost:8008/clean_vram
```

## SE9 (Video IMG)

```bash
# Rebuild
docker compose build ytcaption-se9-make-video-img
docker compose up -d ytcaption-se9-make-video-img

# Testes
cd /root/YTCaption-Easy-Youtube-API/services/se9-make-video-img
python -m pytest tests/ -v

# Health
curl http://localhost:8009/ping
```

## SE10-SE11 (Clothes)

```bash
# SE10 rebuild
docker compose build ytcaption-se10-clothes-segmentation
docker compose up -d ytcaption-se10-clothes-segmentation

# SE11 rebuild
docker compose build ytcaption-se11-clothes-removal
docker compose up -d ytcaption-se11-clothes-removal

# Health
curl http://localhost:8010/ping
curl http://localhost:8011/ping
```

## Shared Library

```bash
cd /root/YTCaption-Easy-Youtube-API/shared
pip install -e .
python -m pytest tests/ -v
```

## Comandos Permitidos

```bash
python -m pytest tests/ -v
python -m py_compile app/main.py
python -m ruff check .
docker compose up -d
docker compose build
```

## Comandos Proibidos Sem Confirmação

```
docker compose down (em produção)
git reset --hard
git clean -fd
rm -rf
migrações destrutivas
instalação global de dependências
```

## Política de Execução

Antes de rodar comandos:
1. Confirmar subprojeto correto.
2. Evitar rodar na raiz.
3. Verificar se o comando é necessário.
4. Evitar comandos longos sem motivo.
5. Evitar alterações colaterais.
6. Não instalar dependências globalmente.
7. Não executar comandos destrutivos.

Se comando falhar:
1. Ler o erro relevante, não o log inteiro.
2. Identificar causa provável.
3. Corrigir se estiver no escopo.
4. Reexecutar somente se fizer sentido.
5. Informar falha se não puder corrigir.
6. Registrar aprendizado durável em memória, se aplicável.
