# 📱 Busca por YouTube Shorts - Resumo Executivo

## 🎯 Visão Geral

Adicionar capacidade de buscar **apenas YouTube Shorts** (vídeos ≤60 segundos) na API, com filtros avançados.

---

## 🏗️ Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────┐
│                    Cliente / Frontend                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Endpoints                           │
│                                                               │
│  POST /search/shorts                                         │
│  POST /search/videos-with-filter                            │
│    └─ shorts_only: bool                                     │
│    └─ exclude_shorts: bool                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Celery Worker (Processor)                       │
│                                                               │
│  async _search_shorts(query, max_results)                   │
│    └─ Executa busca assíncrona                             │
│    └─ Filtra resultados por duração                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  ytbpy Motor de Busca                        │
│                                                               │
│  search_shorts(query, max_results)                          │
│    ├─ Adiciona "shorts" à query                            │
│    ├─ Busca 3x mais resultados                             │
│    ├─ Filtra: duration_seconds ≤ 60                        │
│    └─ Retorna apenas shorts                                │
│                                                               │
│  _extract_reel_item_details(reel_renderer)                  │
│    └─ Extrai dados de reelItemRenderer                     │
│                                                               │
│  is_short(video_info)                                        │
│    ├─ Checa duration_seconds ≤ 60                          │
│    └─ Checa URL pattern '/shorts/'                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Como Identificamos Shorts

### Método 1: Duração (Principal)
```python
is_short = video_info.get('duration_seconds', 999) <= 60
```

### Método 2: URL Pattern
```python
is_short = '/shorts/' in video_info.get('url', '')
```

### Método 3: Renderer Type (YouTube API)
```python
# YouTube usa 'reelItemRenderer' para shorts
is_short = 'reelItemRenderer' in item
```

---

## 📊 Comparação: Vídeos vs Shorts

| Característica | Vídeo Normal | YouTube Short |
|----------------|--------------|---------------|
| **Duração** | Qualquer | ≤ 60 segundos |
| **URL** | `/watch?v=ID` | `/shorts/ID` |
| **Renderer** | `videoRenderer` | `reelItemRenderer` |
| **Formato** | Horizontal/Vertical | Vertical (9:16) |
| **Player** | Player normal | Player de shorts |

---

## 🚀 Novos Endpoints

### 1. Buscar Apenas Shorts
```http
POST /search/shorts?query=programming&max_results=20

Response:
{
  "id": "job_id_123",
  "search_type": "shorts",
  "query": "programming",
  "max_results": 20,
  "status": "queued"
}
```

### 2. Buscar com Filtros
```http
POST /search/videos-with-filter
  ?query=tutorial
  &shorts_only=true
  &max_results=50

OU

POST /search/videos-with-filter
  ?query=tutorial
  &exclude_shorts=true
  &max_results=50
```

---

## 🎨 Exemplo de Resposta

```json
{
  "id": "abc123xyz",
  "search_type": "shorts",
  "status": "completed",
  "result": {
    "query": "funny cats",
    "search_type": "shorts",
    "results_count": 15,
    "total_scanned": 45,
    "results": [
      {
        "video_id": "dQw4w9WgXcQ",
        "title": "Funny Cat Jump",
        "url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "duration": "0:42",
        "duration_seconds": 42,
        "is_short": true,
        "views": 1250000,
        "channel_name": "Cat Videos",
        "thumbnails": {
          "default": "https://...",
          "medium": "https://...",
          "high": "https://..."
        }
      },
      {
        "video_id": "abc123def",
        "title": "Cat Fails Compilation",
        "duration_seconds": 58,
        "is_short": true,
        "views": 890000
      }
    ]
  }
}
```

---

## 🔧 Modificações Necessárias

### Arquivos a Modificar

```
✏️  app/models.py
    └─ Adicionar SearchType.SHORTS
    └─ Adicionar campo is_short: bool

✏️  app/main.py
    └─ Adicionar endpoint /search/shorts
    └─ Adicionar endpoint /search/videos-with-filter

✏️  app/processor.py
    └─ Adicionar método _search_shorts()
    └─ Atualizar process_search_job()

✏️  app/ytbpy/search.py
    └─ Adicionar função search_shorts()
    └─ Adicionar _extract_reel_item_details()
    └─ Adicionar _extract_shorts_from_results()

✏️  app/ytbpy/video.py
    └─ Adicionar função is_short()

📄 tests/test_shorts.py [NOVO]
📄 scripts/test_shorts_feature.sh [NOVO]
```

---

## ⚡ Estratégia de Busca

### Algoritmo de Busca de Shorts

```
1. Entrada: query="programming", max_results=10

2. Otimização da Query:
   enhanced_query = "programming shorts"

3. Over-fetching (buscar mais que o necessário):
   fetch_count = max_results * 3  # 30 resultados

4. Busca Regular:
   results = search_youtube(enhanced_query, fetch_count)

5. Filtragem:
   shorts = filter(results, where duration_seconds <= 60)

6. Limitação:
   return shorts[:max_results]  # Retorna apenas 10

7. Cache:
   Cache key: "shorts:programming:10:24h"
```

### Por que 3x Over-fetching?

- Nem todos resultados são shorts (mix de vídeos normais)
- Garante resultados suficientes após filtragem
- Balanceia performance vs quantidade de resultados

---

## 📈 Benefícios

### Para Usuários
✅ Buscar apenas conteúdo curto (shorts)  
✅ Filtrar shorts de resultados regulares  
✅ Descobrir conteúdo viral em formato short  
✅ Economizar tempo em buscas específicas  

### Para a API
✅ Diferenciação de produto  
✅ Mais granularidade nas buscas  
✅ Melhor experiência do usuário  
✅ Cache otimizado por tipo de conteúdo  

### Técnicos
✅ Código modular e extensível  
✅ Fácil manutenção  
✅ Compatível com sistema existente  
✅ Sem quebrar endpoints atuais  

---

## 🎯 Casos de Uso

### 1. Criadores de Conteúdo
"Quero ver shorts populares sobre 'Python programming' para me inspirar"
```bash
curl -X POST "/search/shorts?query=python+programming&max_results=50"
```

### 2. Plataformas de Agregação
"Mostrar apenas vídeos longos, excluir shorts"
```bash
curl -X POST "/search/videos-with-filter?query=tutorial&exclude_shorts=true"
```

### 3. Apps Mobile
"Feed dedicado de shorts por categoria"
```bash
curl -X POST "/search/shorts?query=fitness&max_results=100"
```

### 4. Análise de Tendências
"Comparar engagement: shorts vs vídeos longos"
```bash
# Buscar shorts
curl -X POST "/search/shorts?query=viral"

# Buscar vídeos longos
curl -X POST "/search/videos-with-filter?query=viral&exclude_shorts=true"
```

---

## ⏱️ Timeline de Implementação

```
Dia 1 (2h):
├─ [✓] Análise e planejamento
├─ [ ] Implementar ytbpy/video.py: is_short()
├─ [ ] Implementar ytbpy/search.py: search_shorts()
└─ [ ] Testes unitários ytbpy

Dia 2 (1.5h):
├─ [ ] Atualizar models.py
├─ [ ] Adicionar endpoints em main.py
├─ [ ] Atualizar processor.py
└─ [ ] Testes de integração

Dia 3 (0.5h):
├─ [ ] Testes end-to-end
├─ [ ] Documentação
├─ [ ] Deploy
└─ [ ] Monitoramento

TOTAL: 4 horas
```

---

## 🧪 Estratégia de Testes

### Testes Automatizados
```bash
# Unit Tests
pytest tests/test_shorts.py -v

# Integration Tests
pytest tests/test_shorts_api.py -v

# E2E Tests
./scripts/test_shorts_feature.sh

# Load Tests
ab -n 100 -c 10 http://localhost:8003/search/shorts?query=test
```

### Métricas de Sucesso
- ✅ 100% dos resultados são shorts (≤60s)
- ✅ Tempo de resposta < 3s para 10 resultados
- ✅ Taxa de cache hit > 70%
- ✅ 0 erros em 100 requisições

---

## 🚨 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| YouTube mudar API | Média | Alto | Monitoramento + testes regulares |
| Performance degradada | Baixa | Médio | Over-fetching controlado + cache |
| Falsos positivos | Média | Baixo | Múltiplos critérios de detecção |
| Cache inconsistente | Baixa | Baixo | TTL adequado + invalidação |

---

## 📚 Documentação

### README.md Update
```markdown
## Buscar YouTube Shorts

### Endpoint
POST /search/shorts

### Parâmetros
- query (string, obrigatório): Termo de busca
- max_results (int, default: 10): Quantidade máxima de shorts

### Exemplo
curl -X POST "http://localhost:8003/search/shorts?query=gaming&max_results=20"

### Resposta
Retorna job ID para acompanhamento via /jobs/{job_id}
```

---

## ✅ Checklist Rápido

- [ ] Ler planejamento completo
- [ ] Aprovar arquitetura
- [ ] Começar implementação ytbpy
- [ ] Testar funções isoladamente
- [ ] Integrar com API
- [ ] Validar endpoints
- [ ] Executar testes automatizados
- [ ] Atualizar documentação
- [ ] Deploy em produção
- [ ] Monitorar métricas

---

## 🤝 Decisão Final

**Implementar busca de shorts?**

✅ **SIM** - Feature valiosa, baixo risco, alta demanda  
❌ **NÃO** - Focar em outras prioridades primeiro  
⏸️ **DEPOIS** - Implementar em sprint futuro  

---

**Documentação completa:** [PLANEJAMENTO_BUSCA_SHORTS.md](./PLANEJAMENTO_BUSCA_SHORTS.md)

**Pronto para implementar!** 🚀
