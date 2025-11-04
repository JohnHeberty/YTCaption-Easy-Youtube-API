# 🐞 BUGLANDIA – Caçada aos 503 pós-Downgrade

## Audio Normalization Service (`services/audio-normalization`)

### Sintoma
- Requisições **GET /health** retornam **503 Service Unavailable** imediatamente após o downgrade de segurança.
- Log do container mostra erro interno durante o health-check.

### Diagnóstico
- O health-check executa `await job_store.redis.ping()`. Entretanto, `job_store.redis` é uma instância síncrona de `redis.Redis` (criada via `Redis.from_url`).
- Chamadas síncronas retornam um `bool`, tornando o `await` inválido e disparando `TypeError: object bool can't be used in 'await' expression`.
- O bloco `except` captura a exceção e marca o serviço como unhealthy, devolvendo 503.

### Ação Recomendada
- Substituir o `await job_store.redis.ping()` por `job_store.redis.ping()` (sem await).
- Aplicar mesma correção em todos os pontos que chamam métodos síncronos do Redis dentro de corrotinas.

---

## Audio Transcriber Service (`services/audio-transcriber`)

### Sintoma
- **GET /health** retorna **503** seguindo o downgrade, com logs semelhantes ao serviço de normalização.

### Diagnóstico
- Mesma causa raiz: `await job_store.redis.ping()` sobre um cliente Redis síncrono.
- Exceção causa fallback para status unhealthy.

### Ação Recomendada
- Remover `await` da chamada `job_store.redis.ping()`.

---

## Video Downloader Service (`services/video-downloader`)

### Sintoma
- Health-check passa a responder **503** após o downgrade.

### Diagnóstico
- Repetição do bug: `await job_store.redis.ping()` com cliente Redis síncrono.
- Erro derruba o health-check e devolve 503, mesmo com serviço operacional.

### Ação Recomendada
- Ajustar health-check para usar `job_store.redis.ping()` sem await.

---

## Resumo Geral
- Todos os microserviços compartilham o mesmo bug de `await` indevido no health-check.
- Corrigir o uso do cliente Redis eliminará os 503 e restabelecerá a sonda de saúde.
- Após ajustes, reexecutar `docker-compose up` e validar `GET /health` em cada serviço.

## Correções Aplicadas
- [x] Audio Normalization: `await job_store.redis.ping()` substituído por chamada síncrona.
- [x] Audio Transcriber: `await job_store.redis.ping()` substituído por chamada síncrona.
- [x] Video Downloader: `await job_store.redis.ping()` substituído por chamada síncrona.
