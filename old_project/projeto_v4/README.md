# Projeto v3 — API local, simples e resiliente (Arquitetura Hexagonal)

Este diretório contém uma nova versão da API, desenhada para uso pessoal e local (rodando dentro do Proxmox, sem acesso de usuários externos). O foco é ser simples, prática e extremamente resiliente em uma máquina com recursos limitados.

## Objetivos
- Baixo consumo de recursos: poucas dependências e processo único.
- Resiliência: timeouts, retries com backoff exponencial, limites de concorrência e desligamento gracioso.
- Manutenibilidade: arquitetura hexagonal separando Domínio, Aplicação (casos de uso), Portas e Adaptadores.
- Operação local: sem requisitos de cloud; armazenamento simples em arquivos.

## Estrutura de pastas
```
projeto_v3/
  app/                # Config, inicialização do FastAPI e wiring de dependências
  domain/             # Entidades e regras de negócio puras
  application/        # Casos de uso e ports (interfaces)
  adapters/           # Entradas (HTTP) e saídas (arquivo, integrações)
  infrastructure/     # Utilitários de resiliência (retry/timeout), etc.
  tests/              # Testes rápidos
  data/               # Saída local (ex.: arquivos de legendas)
  pyproject.toml      # Dependências mínimas
  README.md           # Este arquivo
```

## Resiliência adotada
- Timeout padrão em chamadas externas (evita travamentos).
- Retry com backoff exponencial (falhas transitórias).
- Limitador de concorrência via semáforo (evita sobrecarga num host fraco).
- Logs simples e padronizados.

## Endpoints iniciais

Observação: O provedor de legendas aqui é um “stub” para manter tudo offline e leve. Quando quiser integrar ao YouTube ou outro serviço, crie um novo adaptador Outbound que implemente a mesma Port (ver `application/ports/caption_provider.py`).
## Endpoints iniciais (modo cached-only)
 GET `/health` → status do serviço.
 GET `/version` → versão e configurações básicas.
 GET `/captions/{video_id}/cached` → retorna do cache (sem rede). 404 se não existir.
 POST `/captions/{video_id}` → salva arquivo `.txt` a partir do cache (sem rede). 404 se não existir.

Por padrão, o projeto roda em “cached-only” (sem chamadas externas). Isso o torna mais previsível e leve. Caso deseje ativar busca externa no futuro, podemos plugar um provider e popular o cache — mantendo a mesma Port.

 - CACHED_ONLY (padrão: true)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ./projeto_v3[dev]
```
## Evolução futura (opcional)
 Implementar provider real (YouTube) que preenche o cache (desativando `CACHED_ONLY`), mantendo a mesma Port.
 Adicionar rota para “refresh” do cache quando houver internet.
uvicorn projeto_v3.app.main:app --host 0.0.0.0 --port 8080
```

3) Teste rápido:
```
curl http://localhost:8080/health
```

## Configuração por ambiente (variáveis)
- APP_NAME (padrão: YTCaption v3)
- APP_VERSION (padrão: 0.1.0)
- LOG_LEVEL (padrão: INFO)
- TIMEOUT_SECONDS (padrão: 10)
- MAX_RETRIES (padrão: 2)
- CONCURRENCY_LIMIT (padrão: 4)

Crie um arquivo `.env.local` (opcional) e exporte variáveis antes de rodar.

## Trocar o provedor de legendas
- Implemente `application/ports/caption_provider.py` em um novo adaptador (ex.: `adapters/outbound/youtube_api.py`).
- Envolva chamadas externas com os utilitários de `infrastructure/resilience.py`.
- Faça o wiring em `app/main.py` no lugar do `YouTubeStubProvider`.

## Testes
```
pytest -q projeto_v3/tests
```

## Rodando com Docker

Build e subir com Compose (recomendado):
```
pwsh
cd projeto_v3
docker compose build
docker compose up -d
```

Depois acesse:
```
http://localhost:8080/health
```

Parar:
```
docker compose down
```

Overriding de variáveis (exemplo via docker compose):
```
CACHE_TTL_SECONDS=604800  # 7 dias
CONCURRENCY_LIMIT=2       # host fraco
```

## Performance pré-ajustada

- Docker usa Uvicorn com uvloop + httptools e 1 worker, sem access-log (menos IO). 
- Respostas padrão via ORJSON (JSON mais rápido com baixo overhead).
- Em hosts muito fracos, reduza `CONCURRENCY_LIMIT` para 1–2.
```

## Próximos passos sugeridos
- Implementar adaptador real do YouTube com cache local.
- Adicionar autenticação simples por token local, se necessário.
- Empacotar com Docker apenas se fizer sentido para o host Proxmox (senão rode como serviço do sistema).