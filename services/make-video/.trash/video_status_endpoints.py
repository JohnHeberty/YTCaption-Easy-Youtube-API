"""
Endpoints para gerenciamento do Video Status Store

Adicionar após /admin/queue no main.py
"""


@app.get("/admin/videos/approved")
async def list_approved_videos(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """
    Lista vídeos aprovados
    
    **Use case**: Ver histórico de vídeos aprovados
    
    **Parameters**:
    - limit: Número de resultados (default: 100, max: 1000)
    - offset: Paginação offset (default: 0)
    
    **Returns**: Lista de vídeos aprovados com metadata
    """
    try:
        from .services.video_status_factory import get_video_status_store
        store = get_video_status_store()
        
        approved = store.list_approved(limit=limit, offset=offset)
        total = store.count_approved()
        
        return {
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(approved),
            "videos": approved
        }
    except Exception as e:
        logger.error(f"Error listing approved videos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/videos/rejected")
async def list_rejected_videos(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """
    Lista vídeos reprovados
    
    **Use case**: Ver histórico de vídeos reprovados e motivos
    
    **Parameters**:
    - limit: Número de resultados (default: 100, max: 1000)
    - offset: Paginação offset (default: 0)
    
    **Returns**: Lista de vídeos reprovados com rejection_reason e confidence
    """
    try:
        from .services.video_status_factory import get_video_status_store
        store = get_video_status_store()
        
        rejected = store.list_rejected(limit=limit, offset=offset)
        total = store.count_rejected()
        
        return {
            "status": "success",
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(rejected),
            "videos": rejected
        }
    except Exception as e:
        logger.error(f"Error listing rejected videos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/videos/stats")
async def get_video_stats():
    """
    Estatísticas do banco de vídeos
    
    **Returns**:
    - approved_count: Total de vídeos aprovados
    - rejected_count: Total de vídeos reprovados
    - total_processed: Total de vídeos processados
    - approval_rate: Taxa de aprovação (0-1)
    """
    try:
        from .services.video_status_factory import get_video_status_store
        store = get_video_status_store()
        
        stats = store.get_stats()
        
        return {
            "status": "success",
            "stats": stats,
            "database": {
                "path": store.db_path.name,
                "location": str(store.db_path.parent)
            }
        }
    except Exception as e:
        logger.error(f"Error getting video stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/videos/recover-approved")
async def recover_approved_videos(
    video_ids: List[str] = Query(None, description="IDs específicos para recuperar (opcional)"),
    max_count: int = Query(10, ge=1, le=100, description="Máximo de vídeos para recuperar")
):
    """
    Recupera vídeos aprovados que foram perdidos
    
    **Use case**: Se você perdeu os arquivos MP4 mas tem o histórico no banco,
    pode re-download apenas dos vídeos que foram aprovados anteriormente.
    
    **Parameters**:
    - video_ids: Lista de IDs específicos (opcional)
    - max_count: Máximo para recuperar se video_ids não especificado
    
    **Process**:
    1. Busca vídeos aprovados no banco
    2. Verifica quais arquivos não existem em data/approved/videos/
    3. Re-download via video-downloader
    4. Re-aplica transformação H264
    5. Move para data/approved/videos/
    
    **Returns**: Job ID para monitorar progresso
    """
    try:
        from .services.video_status_factory import get_video_status_store
        store = get_video_status_store()
        
        # Buscar vídeos para recuperar
        if video_ids:
            videos_to_recover = []
            for vid in video_ids:
                approved = store.get_approved(vid)
                if approved:
                    videos_to_recover.append(approved)
        else:
            # Pegar últimos aprovados
            all_approved = store.list_approved(limit=max_count)
            videos_to_recover = all_approved
        
        # Filtrar apenas os que não existem
        missing = []
        for video in videos_to_recover:
            file_path = Path(video.get('file_path', ''))
            if not file_path.exists():
                missing.append(video)
        
        if not missing:
            return {
                "status": "success",
                "message": "Nenhum vídeo aprovado está faltando",
                "checked": len(videos_to_recover),
                "missing": 0
            }
        
        # TODO: Criar job de recuperação (similar ao /download)
        # Por enquanto, retorna lista de vídeos que precisam recuperação
        return {
            "status": "success",
            "message": f"Encontrados {len(missing)} vídeos aprovados faltando",
            "checked": len(videos_to_recover),
            "missing": len(missing),
            "videos": [
                {
                    "video_id": v['video_id'],
                    "title": v.get('title'),
                    "url": v.get('url'),
                    "approved_at": v.get('approved_at'),
                    "expected_path": v.get('file_path')
                }
                for v in missing
            ],
            "hint": "Use POST /download com esses video_ids para recuperar"
        }
        
    except Exception as e:
        logger.error(f"Error recovering approved videos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/videos/clear")
async def clear_video_database(
    target: str = Query(..., regex="^(approved|rejected|all)$", description="O que limpar: approved, rejected, ou all")
):
    """
    ⚠️  CUIDADO: Limpa banco de vídeos
    
    **Use case**: Resetar histórico (NÃO remove arquivos MP4, apenas banco)
    
    **Parameters**:
    - target: 'approved', 'rejected', ou 'all'
    
    **WARNING**: Esta ação é irreversível!
    """
    try:
        from .services.video_status_factory import get_video_status_store
        store = get_video_status_store()
        
        if target == "approved":
            count_before = store.count_approved()
            store.clear_approved()
            return {
                "status": "success",
                "message": f"Cleared {count_before} approved videos from database",
                "warning": "MP4 files NOT deleted, only database records"
            }
        elif target == "rejected":
            count_before = store.count_rejected()
            store.clear_rejected()
            return {
                "status": "success",
                "message": f"Cleared {count_before} rejected videos from database",
                "warning": "Database records cleared"
            }
        elif target == "all":
            approved_count = store.count_approved()
            rejected_count = store.count_rejected()
            store.clear_all()
            return {
                "status": "success",
                "message": f"Cleared ALL video history ({approved_count} approved + {rejected_count} rejected)",
                "warning": "⚠️  ALL video status history has been removed!"
            }
        
    except Exception as e:
        logger.error(f"Error clearing video database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
