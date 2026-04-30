# Erros e Tratamento

## Status HTTP
- 400: request invalida (linguagem nao suportada, arquivo vazio, etc.)
- 404: job/recurso nao encontrado
- 410: job expirado
- 425: transcricao ainda nao concluida
- 500: erro interno
- 503: servico unhealthy (health detalhado)

## Estruturas de erro
O servico pode retornar detail em string ou objeto, por compatibilidade.

Exemplo 400 com detail estruturado:
```json
{
  "detail": {
    "error": "Linguagem de entrada nao suportada",
    "language_provided": "xx",
    "supported_languages": ["auto", "pt", "en"],
    "total_supported": 99,
    "note": "Use GET /languages para ver todas as linguagens suportadas"
  }
}
```

Exemplo 425:
```json
{
  "detail": "Transcricao nao pronta. Status: processing"
}
```

## Boas praticas de cliente
1. Tratar 425 com retry e backoff.
2. Tratar 410 como terminal (nao retentar).
3. Em 500, registrar correlacao por job_id e consultar /jobs/{job_id}.
4. Para jobs travados, usar /jobs/orphaned e /jobs/orphaned/cleanup.
