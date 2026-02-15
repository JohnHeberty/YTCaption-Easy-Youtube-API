"""
Pipeline Service - Download, Transform, Validate, Approve

Gerencia o pipeline completo de vídeos:
1. Download → data/raw/
2. Transform → data/transform/ (conversão H264)
3. Validate → data/validate/ (detecção legendas)
4. Approve → data/approved/ (vídeos finais)
5. Cleanup → Remove das pastas anteriores
6. Blacklist → Vídeos reprovados não são reprocessados
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import httpx
from datetime import datetime

from app.core.config import get_settings
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
from app.services.blacklist_factory import get_blacklist

logger = logging.getLogger(__name__)
settings = get_settings()


class VideoPipeline:
    """
    Pipeline completo para processar vídeos
    
    Fluxo:
    1. Download → data/raw/shorts/
    2. Transform → data/transform/videos/ (H264)
    3. Validate → Detector de legendas (97.73% acurácia)
    4. Approve/Reject:
       - Aprovado: Move para data/approved/videos/
       - Reprovado: Adiciona ao blacklist
    5. Cleanup: Remove de pastas anteriores
    """
    
    def __init__(self):
        self.detector = SubtitleDetectorV2(show_log=True)
        self.blacklist = get_blacklist()  # SQLite blacklist (oficial)
        self.settings = settings
        
        # Criar diretórios
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Garantir que todos os diretórios existem"""
        dirs = [
            'data/raw/shorts',
            'data/transform/videos',
            'data/transform/temp',
            'data/validate/in_progress',
            'data/approved/videos',
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    async def download_shorts(self, query: str, max_count: int = 50) -> List[Dict]:
        """
        1. DOWNLOAD: Buscar e baixar shorts via youtube-search + video-downloader
        
        Args:
            query: Query de busca
            max_count: Máximo de shorts para baixar
        
        Returns:
            Lista de shorts baixados com metadados
        """
        logger.info(f"📥 DOWNLOAD: Buscando shorts para '{query}' (max: {max_count})")
        
        downloaded = []
        
        try:
            # 1. Buscar shorts via youtube-search (assíncrono)
            youtube_search_url = self.settings.get('youtube_search_url')
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 1.1. Criar job de busca
                response = await client.post(
                    f"{youtube_search_url}/search/shorts",
                    params={
                        "query": query,
                        "max_results": max_count
                    }
                )
                response.raise_for_status()
                job_data = response.json()
                job_id = job_data.get('id')
                
                logger.info(f"   📋 Job criado: {job_id} (aguardando...)")
                
                # 1.2. Aguardar job completar
                wait_response = await client.get(
                    f"{youtube_search_url}/jobs/{job_id}/wait",
                    timeout=90.0
                )
                wait_response.raise_for_status()
                completed_job = wait_response.json()
                
                # 1.3. Extrair resultados
                shorts = completed_job.get('result', {}).get('results', [])
            
            logger.info(f"   ✅ {len(shorts)} shorts encontrados")

            # 1.4. Deduplicar por video_id para evitar contagem inflada e sobrescrita
            unique_shorts = []
            seen_video_ids = set()
            duplicated_count = 0

            for short in shorts:
                video_id = short.get('video_id')
                if not video_id:
                    continue

                if video_id in seen_video_ids:
                    duplicated_count += 1
                    continue

                seen_video_ids.add(video_id)
                unique_shorts.append(short)

            if duplicated_count > 0:
                logger.info(
                    f"   🔁 Duplicados removidos: {duplicated_count} "
                    f"(únicos: {len(unique_shorts)})"
                )
            
            # 2. Baixar cada short via video-downloader (assíncrono)
            video_downloader_url = self.settings.get('video_downloader_url')
            
            for i, short in enumerate(unique_shorts, 1):
                video_id = short.get('video_id')
                
                # Verificar blacklist ANTES de baixar
                if self.blacklist.is_blacklisted(video_id):  # Sync call
                    logger.info(f"   ⚫ [{i}/{len(unique_shorts)}] {video_id}: BLACKLISTED (skip)")
                    continue
                
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        # 2.1. Criar job de download
                        response = await client.post(
                            f"{video_downloader_url}/jobs",
                            json={
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "quality": "best"
                            }
                        )
                        response.raise_for_status()
                        job = response.json()
                        job_id = job.get('id')
                        
                        logger.info(f"   📦 [{i}/{len(unique_shorts)}] {video_id}: Job {job_id} criado")
                        
                        # 2.2. Aguardar job completar (polling)
                        max_retries = 30  # 30 tentativas × 2s = 60s timeout 
                        for retry in range(max_retries):
                            await asyncio.sleep(2)
                            status_response = await client.get(
                                f"{video_downloader_url}/jobs/{job_id}"
                            )
                            status_response.raise_for_status()
                            job_status = status_response.json()
                            
                            if job_status.get('status') == 'completed':
                                file_path = job_status.get('file_path')
                                logger.info(f"   ✅ [{i}/{len(unique_shorts)}] {video_id}: Download concluído ({file_path})")
                                break
                            elif job_status.get('status') == 'failed':
                                error_msg = job_status.get('error_message', 'Unknown error')
                                raise Exception(f"Download failed: {error_msg}")
                        else:
                            raise Exception("Download timeout (60s)")
                        
                        # 2.3. Baixar arquivo via GET /jobs/{job_id}/download
                        download_response = await client.get(
                            f"{video_downloader_url}/jobs/{job_id}/download",
                            timeout=60.0
                        )
                        download_response.raise_for_status()
                    
                    # 2.4. Salvar em data/raw/shorts/ com extensão real
                    file_ext = ".mp4"
                    if file_path:
                        parsed_ext = Path(file_path).suffix
                        if parsed_ext:
                            file_ext = parsed_ext

                    video_path = Path(f"data/raw/shorts/{video_id}{file_ext}")
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(video_path, 'wb') as f:
                        f.write(download_response.content)
                    
                    logger.info(f"   💾 [{i}/{len(unique_shorts)}] {video_id}: Salvo em {video_path}")
                    
                    downloaded.append({
                        'video_id': video_id,
                        'title': short.get('title'),
                        'raw_path': str(video_path),
                        'downloaded_at': datetime.utcnow().isoformat()
                    })
                    
                    logger.info(f"   ✅ [{i}/{len(unique_shorts)}] {video_id}: Downloaded")
                    
                except Exception as e:
                    logger.error(f"   ❌ [{i}/{len(unique_shorts)}] {video_id}: Download failed - {e}")
                    continue

                logger.info(f"📥 DOWNLOAD COMPLETO: {len(downloaded)}/{len(unique_shorts)} baixados")
            return downloaded
            
        except Exception as e:
            logger.error(f"❌ Erro no download: {e}", exc_info=True)
            return []
    
    def transform_video(self, video_id: str, raw_path: str) -> Optional[str]:
        """
        2. TRANSFORM: Converter vídeo para H264 compatível
        
        Args:
            video_id: ID do vídeo
            raw_path: Caminho do vídeo bruto (data/raw/)
        
        Returns:
            Caminho do vídeo transformado (data/transform/) ou None se falhou
        """
        logger.info(f"🔄 TRANSFORM: Convertendo {video_id} para H264")
        
        try:
            raw_video = Path(raw_path)
            if not raw_video.exists():
                logger.error(f"   ❌ Arquivo não encontrado: {raw_path}")
                return None
            
            # Caminho de saída
            transform_path = Path(f"data/transform/videos/{video_id}.mp4")
            
            # Conversão FFmpeg para H264
            cmd = [
                'ffmpeg',
                '-i', str(raw_video),
                '-c:v', 'libx264',  # Codec H264
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',  # Sobrescrever
                str(transform_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
            
            if result.returncode == 0 and transform_path.exists():
                logger.info(f"   ✅ Convertido: {transform_path}")
                return str(transform_path)
            else:
                logger.error(f"   ❌ Conversão falhou (code {result.returncode})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro na conversão: {e}", exc_info=True)
            return None
    
    def validate_video(self, video_id: str, transform_path: str) -> Tuple[bool, Dict]:
        """
        3. VALIDATE: Detectar legendas/texto no vídeo
        
        Args:
            video_id: ID do vídeo  
            transform_path: Caminho do vídeo transformado
        
        Returns:
            (aprovado, metadados)
            - aprovado: True se SEM legendas, False se COM legendas
            - metadados: Detalhes da detecção
        """
        logger.info(f"✅ VALIDATE: Detectando legendas em {video_id}")
        
        try:
            # Detecção com SubtitleDetectorV2 (97.73% acurácia)
            has_text, confidence, sample_text, metadata = self.detector.detect(transform_path)
            
            # Aprovado = SEM legendas
            aprovado = not has_text
            
            result_meta = {
                'video_id': video_id,
                'has_text': has_text,
                'confidence': confidence,
                'sample_text': sample_text,
                'frames_processed': metadata.get('frames_processed', 0),
                'frames_with_text': metadata.get('frames_with_text', 0),
                'detection_ratio': metadata.get('detection_ratio', 0.0),
                'validated_at': datetime.utcnow().isoformat()
            }
            
            if aprovado:
                logger.info(f"   ✅ APROVADO: {video_id} (SEM legendas, conf: {confidence:.2f})")
            else:
                logger.info(f"   ❌ REPROVADO: {video_id} (COM legendas, conf: {confidence:.2f})")
                logger.info(f"      Texto detectado: '{sample_text[:100]}'")
            
            return aprovado, result_meta
            
        except Exception as e:
            logger.error(f"❌ Erro na validação: {e}", exc_info=True)
            # Em caso de erro, rejeitar por segurança
            return False, {'error': str(e), 'video_id': video_id}
    
    async def approve_video(self, video_id: str, transform_path: str, metadata: Dict):
        """
        4a. APPROVE: Mover vídeo aprovado para data/approved/
        
        Args:
            video_id: ID do vídeo
            transform_path: Caminho do vídeo transformado
            metadata: Metadados da validação
        """
        logger.info(f"✅ APPROVE: Movendo {video_id} para approved/")
        
        try:
            transform_video = Path(transform_path)
            approved_path = Path(f"data/approved/videos/{video_id}.mp4")
            
            # Mover (não copiar) para economizar espaço
            if transform_video.exists():
                transform_video.rename(approved_path)
                logger.info(f"   ✅ Movido: {approved_path}")
            
            # Limpar pastas anteriores
            await self._cleanup_previous_stages(video_id)
            
        except Exception as e:
            logger.error(f"❌ Erro ao aprovar: {e}", exc_info=True)
    
    async def reject_video(self, video_id: str, metadata: Dict):
        """
        4b. REJECT: Adicionar ao blacklist e limpar
        
        Args:
            video_id: ID do vídeo
            metadata: Metadados da validação (motivo da rejeição)
        """
        logger.info(f"❌ REJECT: Adicionando {video_id} ao blacklist")
        
        try:
            # Adicionar ao blacklist
            confidence = metadata.get('confidence', 0.0)
            reason = f"Legendas detectadas (conf: {confidence:.2f})"
            self.blacklist.add(  # Sync call
                video_id=video_id,
                reason=reason,
                confidence=confidence,
                metadata=metadata
            )
            
            logger.info(f"   ⚫ Blacklisted: {video_id}")
            
            # Limpar todas as pastas
            await self._cleanup_all_stages(video_id)
            
        except Exception as e:
            logger.error(f"❌ Erro ao rejeitar: {e}", exc_info=True)
    
    async def _cleanup_previous_stages(self, video_id: str):
        """
        5. CLEANUP: Remover vídeo de pastas anteriores (aprovado)
        
        Remove de:
        - data/raw/shorts/
        - data/transform/videos/
        """
        logger.info(f"🧹 CLEANUP: Removendo {video_id} de pastas anteriores")
        
        raw_dir = Path("data/raw/shorts")
        transform_dir = Path("data/transform/videos")

        # Remove todas as variantes de extensão no raw (ex: .mp4, .webm, .mkv)
        for path in raw_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info(f"   🗑️  Removido: {path}")

        # Remove transformado (normalmente .mp4)
        for path in transform_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info(f"   🗑️  Removido: {path}")
    
    async def _cleanup_all_stages(self, video_id: str):
        """
        5. CLEANUP: Remover vídeo de TODAS as pastas (rejeitado)
        
        Remove de:
        - data/raw/shorts/
        - data/transform/videos/
        - data/validate/in_progress/
        - data/approved/videos/ (se existir)
        """
        logger.info(f"🧹 CLEANUP COMPLETO: Removendo {video_id} de todas as pastas")
        
        stage_dirs = [
            Path("data/raw/shorts"),
            Path("data/transform/videos"),
            Path("data/validate/in_progress"),
            Path("data/approved/videos"),
        ]

        for stage_dir in stage_dirs:
            for path in stage_dir.glob(f"{video_id}.*"):
                if path.is_file():
                    path.unlink()
                    logger.info(f"   🗑️  Removido: {path}")
    
    async def process_pipeline(self, query: str, max_shorts: int = 50) -> Dict:
        """
        Pipeline completo: Download → Transform → Validate → Approve/Reject
        
        Args:
            query: Query de busca
            max_shorts: Máximo de shorts para processar
        
        Returns:
            Estatísticas do pipeline
        """
        logger.info(f"🚀 PIPELINE INICIADO: '{query}' (max: {max_shorts})")
        
        stats = {
            'query': query,
            'downloaded': 0,
            'transformed': 0,
            'approved': 0,
            'rejected': 0,
            'errors': 0,
            'start_time': datetime.utcnow().isoformat()
        }
        
        # 1. DOWNLOAD
        shorts = await self.download_shorts(query, max_shorts)
        stats['downloaded'] = len(shorts)
        
        if not shorts:
            logger.warning("⚠️  Nenhum short baixado. Pipeline finalizado.")
            stats['end_time'] = datetime.utcnow().isoformat()
            return stats
        
        # 2. TRANSFORM + 3. VALIDATE + 4. APPROVE/REJECT
        processed_video_ids = set()

        for short in shorts:
            video_id = short['video_id']
            raw_path = short['raw_path']

            if video_id in processed_video_ids:
                logger.info(f"   🔁 DUPLICADO no pipeline final (skip): {video_id}")
                continue

            processed_video_ids.add(video_id)
            
            try:
                # 2. Transform
                transform_path = self.transform_video(video_id, raw_path)
                if not transform_path:
                    stats['errors'] += 1
                    await self._cleanup_all_stages(video_id)
                    continue
                stats['transformed'] += 1
                
                # 3. Validate
                aprovado, metadata = self.validate_video(video_id, transform_path)
                
                # 4. Approve ou Reject
                if aprovado:
                    await self.approve_video(video_id, transform_path, metadata)
                    stats['approved'] += 1
                else:
                    await self.reject_video(video_id, metadata)
                    stats['rejected'] += 1
                
            except Exception as e:
                logger.error(f"❌ Erro processando {video_id}: {e}", exc_info=True)
                stats['errors'] += 1
                await self._cleanup_all_stages(video_id)
                continue
        
        stats['end_time'] = datetime.utcnow().isoformat()
        
        logger.info(f"🎉 PIPELINE COMPLETO:")
        logger.info(f"   📥 Downloaded: {stats['downloaded']}")
        logger.info(f"   🔄 Transformed: {stats['transformed']}")
        logger.info(f"   ✅ Approved: {stats['approved']}")
        logger.info(f"   ❌ Rejected: {stats['rejected']}")
        logger.info(f"   ⚠️  Errors: {stats['errors']}")
        
        return stats
