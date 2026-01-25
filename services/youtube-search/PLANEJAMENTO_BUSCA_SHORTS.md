# 📱 Planejamento: Implementação de Busca por YouTube Shorts

**Data:** 25 de Janeiro de 2026  
**Feature:** Busca exclusiva por YouTube Shorts  
**Complexidade:** Média  
**Tempo Estimado:** 3-4 horas

---

## 🎯 Objetivo

Adicionar funcionalidade de busca específica por YouTube Shorts na API, permitindo:
- Buscar apenas shorts (vídeos curtos ≤60 segundos)
- Filtrar resultados de busca normal para incluir/excluir shorts
- Identificar shorts automaticamente nas buscas regulares

---

## 🔍 Análise do Motor ytbpy

### Estrutura Atual
```
ytbpy/
├── search.py       - Busca geral de vídeos (inclui shorts misturados)
├── video.py        - Informações detalhadas de vídeos
├── channel.py      - Informações de canais
├── playlist.py     - Informações de playlists
└── utils.py        - Funções auxiliares
```

### Como o YouTube Identifica Shorts

**1. URL Pattern:**
```
Vídeo normal: https://www.youtube.com/watch?v={video_id}
Short:        https://www.youtube.com/shorts/{video_id}
```

**2. Duração:**
- Shorts têm duração máxima de 60 segundos (≤60s)
- No código atual, já extraímos `duration_seconds`

**3. Na API InnerTube:**
- Campo `reelItemRenderer` ao invés de `videoRenderer`
- Metadata específica em `playerMicroformatRenderer`

---

## 📋 Plano de Implementação

### Fase 1: Modificações no Core (ytbpy)

#### 1.1. Adicionar Função de Detecção de Shorts (`ytbpy/video.py`)

```python
def is_short(video_info: Dict[str, Any]) -> bool:
    """
    Determine if a video is a YouTube Short
    
    Criteria:
    - Duration ≤ 60 seconds
    - May have specific metadata flags
    """
    duration_seconds = video_info.get('duration_seconds', 0)
    
    # Primary check: duration
    if duration_seconds > 0 and duration_seconds <= 60:
        return True
    
    # Secondary check: URL pattern (if available)
    url = video_info.get('url', '')
    if '/shorts/' in url:
        return True
    
    return False
```

#### 1.2. Criar Função de Busca de Shorts (`ytbpy/search.py`)

```python
def search_shorts(query, max_results=10, timeout=10):
    """
    Search specifically for YouTube Shorts
    
    Strategy:
    1. Add 'shorts' to search query to bias results
    2. Perform regular search
    3. Filter results by duration (≤60s)
    4. Continue pagination until enough shorts found
    """
    
    # Enhance query to find shorts
    enhanced_query = f"{query} shorts"
    
    # Perform search
    results = search_youtube(enhanced_query, max_results * 3, timeout)
    
    if results.get('error'):
        return results
    
    # Filter for shorts only
    shorts_only = [
        video for video in results.get('results', [])
        if video.get('duration_seconds', 999) <= 60
    ]
    
    return {
        "query": query,
        "search_type": "shorts",
        "results_count": len(shorts_only[:max_results]),
        "total_scanned": results.get('results_count', 0),
        "results": shorts_only[:max_results]
    }
```

#### 1.3. Adicionar Extração de Shorts em Resultados (`ytbpy/search.py`)

```python
def _extract_shorts_from_results(initial_data, max_results=10):
    """
    Extract shorts from search results using reelItemRenderer
    
    YouTube may return shorts with different renderer structure
    """
    shorts_results = []
    
    try:
        contents = (
            initial_data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for content in contents:
            item_section = content.get("itemSectionRenderer", {})
            if item_section:
                items = item_section.get("contents", [])

                for item in items:
                    # Check for reelItemRenderer (shorts specific)
                    reel_renderer = item.get("reelItemRenderer", {})
                    
                    if reel_renderer:
                        short_info = _extract_reel_item_details(reel_renderer)
                        if short_info:
                            shorts_results.append(short_info)
                    
                    # Also check regular videoRenderer with short duration
                    video_renderer = item.get("videoRenderer", {})
                    if video_renderer:
                        video_info = _extract_search_video_details(video_renderer)
                        if video_info and video_info.get('duration_seconds', 999) <= 60:
                            video_info['is_short'] = True
                            shorts_results.append(video_info)
                    
                    if len(shorts_results) >= max_results:
                        break

    except Exception as e:
        return {"error": f"Error parsing shorts results: {str(e)}"}

    return shorts_results


def _extract_reel_item_details(reel_renderer):
    """
    Extract details from reelItemRenderer (shorts-specific structure)
    """
    if not reel_renderer:
        return None
    
    video_id = reel_renderer.get("videoId")
    if not video_id:
        return None
    
    short_info = {
        "video_id": video_id,
        "thumbnails": get_thumbnail_urls(video_id),
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "is_short": True
    }
    
    # Extract title
    headline = reel_renderer.get("headline", {})
    if headline:
        title_runs = headline.get("runs", []) or headline.get("simpleText", "")
        if isinstance(title_runs, list):
            short_info["title"] = "".join(run.get("text", "") for run in title_runs)
        else:
            short_info["title"] = title_runs
    
    # Extract view count
    view_count_text = reel_renderer.get("viewCountText", {}).get("simpleText", "")
    if view_count_text:
        view_match = re.search(r"(\d+(?:,\d+)*)", view_count_text)
        if view_match:
            short_info["views"] = int(view_match.group(1).replace(",", ""))
    
    return short_info
```

---

### Fase 2: Modificações na API (Backend)

#### 2.1. Atualizar Models (`app/models.py`)

```python
class SearchType(str, Enum):
    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    VIDEO_INFO = "video_info"
    CHANNEL_INFO = "channel_info"
    PLAYLIST_INFO = "playlist_info"
    RELATED_VIDEOS = "related_videos"
    SHORTS = "shorts"  # ← NOVO
    RELATED_SHORTS = "related_shorts"  # ← NOVO (opcional)


class SearchRequest(BaseModel):
    """Request for YouTube search operations"""
    query: Optional[str] = None
    video_id: Optional[str] = None
    channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    search_type: SearchType = SearchType.VIDEO
    max_results: int = Field(default=10, ge=1)
    include_videos: bool = False
    shorts_only: bool = False  # ← NOVO: Filter para buscar apenas shorts
    exclude_shorts: bool = False  # ← NOVO: Excluir shorts dos resultados


class VideoInfo(BaseModel):
    """Video information model"""
    video_id: str
    title: Optional[str] = None
    # ... existing fields ...
    is_short: Optional[bool] = False  # ← NOVO
```

#### 2.2. Adicionar Endpoint de Busca de Shorts (`app/main.py`)

```python
@app.post("/search/shorts", response_model=Job)
async def search_shorts(query: str, max_results: int = 10) -> Job:
    """
    Search for YouTube Shorts only
    
    - **query**: Search query
    - **max_results**: Maximum number of shorts to return (unlimited)
    
    Returns only videos with duration ≤60 seconds
    """
    try:
        logger.info(f"Search shorts request: '{query}' (max: {max_results})")
        
        if max_results < 1:
            raise InvalidRequestError("max_results must be at least 1")
        
        new_job = Job.create_new(
            search_type=SearchType.SHORTS,
            query=query,
            max_results=max_results,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                logger.info(f"Job {new_job.id} already completed (cache hit)")
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                logger.info(f"Job {new_job.id} is processing")
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created and submitted to Celery")
        return new_job
        
    except InvalidRequestError:
        raise
    except Exception as e:
        logger.error(f"Error creating shorts search job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/videos-with-filter", response_model=Job)
async def search_videos_filtered(
    query: str, 
    max_results: int = 10,
    shorts_only: bool = False,
    exclude_shorts: bool = False
) -> Job:
    """
    Search videos with shorts filter options
    
    - **query**: Search query
    - **max_results**: Maximum number of results
    - **shorts_only**: Return only shorts (≤60s)
    - **exclude_shorts**: Exclude shorts from results
    """
    try:
        logger.info(f"Filtered search: '{query}' (shorts_only={shorts_only}, exclude={exclude_shorts})")
        
        if max_results < 1:
            raise InvalidRequestError("max_results must be at least 1")
        
        if shorts_only and exclude_shorts:
            raise InvalidRequestError("Cannot use both shorts_only and exclude_shorts")
        
        # Determine search type
        search_type = SearchType.SHORTS if shorts_only else SearchType.VIDEO
        
        new_job = Job.create_new(
            search_type=search_type,
            query=query,
            max_results=max_results,
            cache_ttl_hours=settings['cache_ttl_hours']
        )
        
        # Store filter preferences in job metadata (if needed)
        # This would require adding a metadata field to Job model
        
        existing_job = job_store.get_job(new_job.id)
        
        if existing_job:
            if existing_job.status == JobStatus.COMPLETED:
                return existing_job
            elif existing_job.status == JobStatus.PROCESSING:
                return existing_job
        
        job_store.save_job(new_job)
        submit_celery_task(new_job)
        
        logger.info(f"Job {new_job.id} created")
        return new_job
        
    except InvalidRequestError:
        raise
    except Exception as e:
        logger.error(f"Error creating filtered search job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2.3. Atualizar Processor (`app/processor.py`)

```python
async def process_search_job(self, job: Job) -> Job:
    """Process a search job asynchronously"""
    try:
        logger.info(f"🔍 Processing search job {job.id} - Type: {job.search_type.value}")
        
        job.status = JobStatus.PROCESSING
        job.progress = 10.0
        if self.job_store:
            self.job_store.update_job(job)
        
        result = None
        
        if job.search_type == SearchType.VIDEO_INFO:
            result = await self._get_video_info(job.video_id)
        elif job.search_type == SearchType.CHANNEL_INFO:
            result = await self._get_channel_info(job.channel_id, job.include_videos)
        elif job.search_type == SearchType.PLAYLIST_INFO:
            result = await self._get_playlist_info(job.playlist_id)
        elif job.search_type == SearchType.VIDEO:
            result = await self._search_videos(job.query, job.max_results)
        elif job.search_type == SearchType.RELATED_VIDEOS:
            result = await self._get_related_videos(job.video_id, job.max_results)
        elif job.search_type == SearchType.SHORTS:  # ← NOVO
            result = await self._search_shorts(job.query, job.max_results)
        else:
            raise YouTubeSearchException(f"Unsupported search type: {job.search_type}")
        
        # ... rest of the method
        
    except Exception as e:
        # ... error handling


async def _search_shorts(self, query: str, max_results: int = 10) -> Dict[str, Any]:
    """Search for YouTube Shorts only"""
    try:
        logger.info(f"📱 Searching shorts: '{query}' (max: {max_results})")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            ytb_search.search_shorts,
            query,
            max_results,
            self.timeout
        )
        
        if result.get('error'):
            raise YouTubeAPIError(result['error'])
        
        return result
        
    except Exception as e:
        logger.error(f"Error searching shorts: {e}")
        raise YouTubeAPIError(f"Failed to search shorts: {str(e)}")
```

---

### Fase 3: Melhorias e Features Adicionais

#### 3.1. Enriquecimento de Dados

```python
# Adicionar flag is_short em todas as buscas
def _enrich_video_with_short_flag(video_info: Dict[str, Any]) -> Dict[str, Any]:
    """Add is_short flag to video info"""
    duration = video_info.get('duration_seconds', 0)
    url = video_info.get('url', '')
    
    video_info['is_short'] = (duration > 0 and duration <= 60) or '/shorts/' in url
    
    return video_info
```

#### 3.2. Filtros Avançados

```python
def filter_videos_by_type(
    videos: List[Dict[str, Any]], 
    shorts_only: bool = False,
    exclude_shorts: bool = False
) -> List[Dict[str, Any]]:
    """
    Filter video list based on shorts preferences
    """
    if not shorts_only and not exclude_shorts:
        return videos
    
    filtered = []
    for video in videos:
        is_short = video.get('duration_seconds', 999) <= 60
        
        if shorts_only and is_short:
            filtered.append(video)
        elif exclude_shorts and not is_short:
            filtered.append(video)
        elif not shorts_only and not exclude_shorts:
            filtered.append(video)
    
    return filtered
```

---

## 🧪 Plano de Testes

### Testes Unitários (ytbpy)

```python
# test_shorts_detection.py

def test_is_short_by_duration():
    video_info = {"duration_seconds": 30}
    assert is_short(video_info) == True

def test_is_not_short_by_duration():
    video_info = {"duration_seconds": 120}
    assert is_short(video_info) == False

def test_is_short_by_url():
    video_info = {"url": "https://www.youtube.com/shorts/abc123"}
    assert is_short(video_info) == True

def test_search_shorts():
    results = search_shorts("python tutorial", max_results=5)
    assert results.get('search_type') == 'shorts'
    assert all(v.get('duration_seconds', 999) <= 60 for v in results['results'])
```

### Testes de Integração (API)

```bash
# 1. Buscar shorts
curl -X POST "http://localhost:8003/search/shorts?query=programming&max_results=20"

# 2. Buscar vídeos excluindo shorts
curl -X POST "http://localhost:8003/search/videos-with-filter?query=tutorial&exclude_shorts=true"

# 3. Buscar apenas shorts com filtro
curl -X POST "http://localhost:8003/search/videos-with-filter?query=python&shorts_only=true"
```

### Script de Teste Automatizado

```bash
#!/bin/bash
# test_shorts_feature.sh

echo "=== Testing Shorts Feature ==="

# Test 1: Search shorts endpoint
echo "1. Testing /search/shorts..."
response=$(curl -s -X POST "http://localhost:8003/search/shorts?query=funny&max_results=10")
job_id=$(echo "$response" | jq -r '.id')
echo "Job ID: $job_id"

# Wait for completion
sleep 15

# Check results
result=$(curl -s "http://localhost:8003/jobs/$job_id")
status=$(echo "$result" | jq -r '.status')
count=$(echo "$result" | jq -r '.result.results_count')

echo "Status: $status"
echo "Results: $count shorts found"

# Verify all are shorts (≤60s)
echo "$result" | jq -r '.result.results[] | .duration_seconds' | while read duration; do
    if [ "$duration" -gt 60 ]; then
        echo "ERROR: Found video with duration > 60s: $duration"
        exit 1
    fi
done

echo "✓ All results are valid shorts"
```

---

## 📊 Estrutura de Arquivos Modificados

```
services/youtube-search/
├── app/
│   ├── models.py                 [MODIFICAR] - Adicionar SearchType.SHORTS
│   ├── main.py                   [MODIFICAR] - Adicionar endpoints
│   ├── processor.py              [MODIFICAR] - Adicionar _search_shorts()
│   └── ytbpy/
│       ├── search.py             [MODIFICAR] - Adicionar search_shorts()
│       │                                      - Adicionar _extract_shorts_from_results()
│       │                                      - Adicionar _extract_reel_item_details()
│       └── video.py              [MODIFICAR] - Adicionar is_short()
│
├── tests/
│   ├── test_shorts.py            [CRIAR] - Testes de shorts
│   └── test_shorts_api.py        [CRIAR] - Testes de API
│
└── scripts/
    └── test_shorts_feature.sh    [CRIAR] - Script de teste
```

---

## 📝 Checklist de Implementação

### Fase 1: Core (ytbpy)
- [ ] Implementar `is_short()` em `video.py`
- [ ] Implementar `search_shorts()` em `search.py`
- [ ] Implementar `_extract_reel_item_details()` em `search.py`
- [ ] Implementar `_extract_shorts_from_results()` em `search.py`
- [ ] Adicionar testes unitários

### Fase 2: API Backend
- [ ] Atualizar `SearchType` enum em `models.py`
- [ ] Adicionar campo `is_short` em `VideoInfo` model
- [ ] Implementar endpoint `/search/shorts` em `main.py`
- [ ] Implementar endpoint `/search/videos-with-filter` em `main.py`
- [ ] Atualizar `process_search_job()` em `processor.py`
- [ ] Implementar `_search_shorts()` em `processor.py`

### Fase 3: Testes e Validação
- [ ] Criar testes unitários para funções ytbpy
- [ ] Criar testes de integração para API
- [ ] Criar script de teste automatizado
- [ ] Testar com diferentes queries
- [ ] Validar performance com max_results alto

### Fase 4: Documentação
- [ ] Atualizar README.md com novos endpoints
- [ ] Atualizar documentação da API (Swagger/OpenAPI)
- [ ] Adicionar exemplos de uso
- [ ] Documentar diferenças entre shorts e vídeos regulares

---

## 🔧 Configurações Adicionais

### Possíveis Parâmetros de Config (`config.py`)

```python
YOUTUBE_SHORTS_CONFIG = {
    "max_duration_seconds": 60,  # Duração máxima para considerar short
    "search_multiplier": 3,      # Multiplicador para buscar mais resultados e filtrar
    "enable_reel_renderer": True, # Usar reelItemRenderer quando disponível
}
```

---

## ⚠️ Considerações e Limitações

### Limitações Técnicas

1. **API Não Oficial**
   - YouTube pode mudar estrutura HTML/JSON a qualquer momento
   - Necessário monitoramento e manutenção

2. **Detecção de Shorts**
   - Baseada principalmente em duração (≤60s)
   - Alguns vídeos curtos normais podem ser classificados como shorts
   - URL pattern (`/shorts/`) nem sempre disponível em resultados de busca

3. **Performance**
   - Busca de shorts pode requerer mais requisições
   - Filtrar por duração requer buscar mais resultados do que solicitado

### Melhorias Futuras

1. **Machine Learning**
   - Usar ML para detectar características visuais de shorts
   - Analisar formato vertical (9:16)

2. **Cache Inteligente**
   - Cache separado para shorts vs vídeos normais
   - Invalidação baseada em duração

3. **Estatísticas**
   - Ratio shorts/vídeos em buscas
   - Trending shorts por categoria

---

## 🎯 Resultado Esperado

### Novos Endpoints

```
POST /search/shorts
  ?query=string
  &max_results=int
  
POST /search/videos-with-filter
  ?query=string
  &max_results=int
  &shorts_only=bool
  &exclude_shorts=bool
```

### Resposta Exemplo

```json
{
  "id": "abc123",
  "search_type": "shorts",
  "query": "funny cats",
  "max_results": 10,
  "status": "completed",
  "result": {
    "query": "funny cats",
    "search_type": "shorts",
    "results_count": 10,
    "total_scanned": 30,
    "results": [
      {
        "video_id": "xyz789",
        "title": "Funny Cat Moment",
        "url": "https://www.youtube.com/shorts/xyz789",
        "duration": "0:45",
        "duration_seconds": 45,
        "is_short": true,
        "views": 1500000,
        "thumbnails": {...}
      }
    ]
  }
}
```

---

## ⏱️ Estimativa de Tempo

| Fase | Atividade | Tempo Estimado |
|------|-----------|----------------|
| 1 | Implementação ytbpy | 1.5 horas |
| 2 | Implementação API | 1 hora |
| 3 | Testes | 0.5 hora |
| 4 | Documentação | 0.5 hora |
| **TOTAL** | | **3.5 horas** |

---

## ✅ Próximos Passos

1. Revisar e aprovar este planejamento
2. Começar implementação pela Fase 1 (ytbpy)
3. Testar cada componente individualmente
4. Integrar com API
5. Validar com testes end-to-end
6. Documentar e fazer deploy

**Pronto para começar a implementação?** 🚀
