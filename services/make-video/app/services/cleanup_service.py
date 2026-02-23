"""
Cleanup Service
Serviço de limpeza periódica que roda a cada 10 minutos

Responsabilidades:
- Detecta arquivos órfãos (vídeos sem tracking no banco)
- Cataloga erros no VideoStatusStore
- Remove arquivos temporários antigos
- Limpa cache de shorts expirados
- Monitora uso de disco

Design:
- Background task assíncrono
- Intervalo configurável (default: 10 min)
- Relatório de ações realizadas
- Não para o serviço em caso de erro
"""

import asyncio
import logging
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class CleanupService:
    """
    Serviço de limpeza periódica para manter o sistema organizado
    
    Features:
    - Detecta e cataloga vídeos órfãos
    - Remove arquivos temporários antigos
    - Limpa cache expirado
    - Relatório de ações
    """
    
    def __init__(
        self,
        video_status_store,
        data_dir: str = "./data",
        cleanup_interval_minutes: int = 10,
        orphan_retention_hours: int = 24,
        temp_retention_hours: int = 6
    ):
        """
        Args:
            video_status_store: VideoStatusStore instance
            data_dir: Diretório raiz dos dados
            cleanup_interval_minutes: Intervalo entre execuções (default: 10min)
            orphan_retention_hours: Horas antes de considerar arquivo órfão (default: 24h)
            temp_retention_hours: Horas antes de limpar temporários (default: 6h)
        """
        self.status_store = video_status_store
        self.data_dir = Path(data_dir)
        self.cleanup_interval = cleanup_interval_minutes * 60  # em segundos
        self.orphan_retention = orphan_retention_hours * 3600  # em segundos
        self.temp_retention = temp_retention_hours * 3600  # em segundos
        
        # Diretórios monitorados
        self.raw_dir = self.data_dir / "raw" / "shorts"
        self.transform_dir = self.data_dir / "transform" / "videos"
        self.approved_dir = self.data_dir / "approved" / "videos"
        self.temp_dir = self.data_dir / "raw" / "temp"
        
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"🧹 CleanupService initialized (interval: {cleanup_interval_minutes}min)")
    
    async def start(self):
        """Inicia o serviço de limpeza em background"""
        if self._running:
            logger.warning("CleanupService already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("✅ CleanupService started")
    
    async def stop(self):
        """Para o serviço de limpeza"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 CleanupService stopped")
    
    async def _cleanup_loop(self):
        """Loop principal de limpeza"""
        while self._running:
            try:
                # Aguardar intervalo
                await asyncio.sleep(self.cleanup_interval)
                
                # Executar limpeza
                logger.info("🧹 Starting cleanup cycle...")
                report = await self.run_cleanup()
                
                # Log resumo
                logger.info(
                    f"✅ Cleanup completed: "
                    f"orphans={report['orphans_found']}, "
                    f"temp_cleaned={report['temp_files_cleaned']}, "
                    f"errors_cataloged={report['errors_cataloged']}"
                )
                
            except asyncio.CancelledError:
                logger.info("CleanupService loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                logger.debug(traceback.format_exc())
                # Continuar mesmo com erro
                await asyncio.sleep(60)  # Wait 1min antes de retry
    
    async def run_cleanup(self) -> Dict:
        """
        Executa um ciclo completo de limpeza
        
        Returns:
            Relatório com estatísticas de limpeza
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "orphans_found": 0,
            "orphans_cataloged": 0,
            "temp_files_cleaned": 0,
            "cache_size_mb": 0,
            "errors_cataloged": 0,
            "actions": []
        }
        
        try:
            # 1. Detectar e catalogar órfãos em raw/
            orphans_raw = await self._find_orphans(self.raw_dir, "raw")
            report["orphans_found"] += len(orphans_raw)
            
            for video_id, file_path, reason in orphans_raw:
                self._catalog_orphan(video_id, file_path, "raw", reason)
                report["orphans_cataloged"] += 1
                report["errors_cataloged"] += 1
            
            # 2. Detectar e catalogar órfãos em transform/
            orphans_transform = await self._find_orphans(self.transform_dir, "transform")
            report["orphans_found"] += len(orphans_transform)
            
            for video_id, file_path, reason in orphans_transform:
                self._catalog_orphan(video_id, file_path, "transform", reason)
                report["orphans_cataloged"] += 1
                report["errors_cataloged"] += 1
            
            # 3. Limpar arquivos temporários antigos
            temp_cleaned = await self._clean_temp_files()
            report["temp_files_cleaned"] = temp_cleaned
            
            # 4. Calcular uso de disco
            cache_size = await self._calculate_cache_size()
            report["cache_size_mb"] = cache_size
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.debug(traceback.format_exc())
            report["actions"].append(f"ERROR: {str(e)}")
        
        return report
    
    async def _find_orphans(self, directory: Path, stage: str) -> List[Tuple[str, Path, str]]:
        """
        Encontra arquivos órfãos em um diretório
        
        Órfão = arquivo MP4 que:
        - Não está no banco (approved/rejected/error)
        - Tem mais de N horas de idade
        
        Returns:
            Lista de (video_id, file_path, reason)
        """
        orphans = []
        
        if not directory.exists():
            return orphans
        
        now = datetime.now().timestamp()
        threshold = now - self.orphan_retention
        
        try:
            for mp4_file in directory.glob("*.mp4"):
                # Extrair video_id do nome do arquivo
                video_id = mp4_file.stem
                
                # Verificar idade do arquivo
                file_mtime = mp4_file.stat().st_mtime
                if file_mtime > threshold:
                    # Arquivo muito recente, ainda pode estar em processamento
                    continue
                
                # Verificar se está no banco
                is_tracked = (
                    self.status_store.is_approved(video_id) or
                    self.status_store.is_rejected(video_id) or
                    self.status_store.is_error(video_id)
                )
                
                if not is_tracked:
                    age_hours = (now - file_mtime) / 3600
                    reason = f"Orphan file in {stage}/ (age: {age_hours:.1f}h, no DB entry)"
                    orphans.append((video_id, mp4_file, reason))
                    logger.warning(f"🔍 Orphan detected: {mp4_file} ({reason})")
        
        except Exception as e:
            logger.error(f"Error scanning {directory}: {e}")
        
        return orphans
    
    def _catalog_orphan(self, video_id: str, file_path: Path, stage: str, reason: str):
        """
        Cataloga um arquivo órfão no banco de erros e o remove
        
        Args:
            video_id: ID do vídeo
            file_path: Caminho do arquivo órfão
            stage: Stage onde foi encontrado (raw/transform/approved)
            reason: Motivo do erro
        """
        try:
            # Registrar no banco
            self.status_store.add_error(
                video_id=video_id,
                error_type="orphan_file",
                error_message=reason,
                file_path=str(file_path),
                stage=stage,
                retry_count=0,
                metadata={
                    "cleanup_timestamp": datetime.now().isoformat(),
                    "file_size_mb": file_path.stat().st_size / (1024 * 1024)
                }
            )
            
            # Remover arquivo órfão
            file_path.unlink()
            logger.info(f"🗑️  Orphan removed: {file_path}")
            
        except Exception as e:
            logger.error(f"Error cataloging orphan {video_id}: {e}")
    
    async def _clean_temp_files(self) -> int:
        """
        Remove arquivos temporários antigos
        
        Returns:
            Número de arquivos removidos
        """
        if not self.temp_dir.exists():
            return 0
        
        cleaned = 0
        now = datetime.now().timestamp()
        threshold = now - self.temp_retention
        
        try:
            for temp_file in self.temp_dir.rglob("*"):
                if not temp_file.is_file():
                    continue
                
                file_mtime = temp_file.stat().st_mtime
                if file_mtime < threshold:
                    temp_file.unlink()
                    cleaned += 1
                    logger.debug(f"🗑️  Temp file removed: {temp_file}")
        
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
        
        return cleaned
    
    async def _calculate_cache_size(self) -> float:
        """
        Calcula tamanho total do cache em MB
        
        Returns:
            Tamanho em MB
        """
        total_bytes = 0
        
        for directory in [self.raw_dir, self.transform_dir, self.approved_dir]:
            if not directory.exists():
                continue
            
            try:
                for mp4_file in directory.glob("*.mp4"):
                    total_bytes += mp4_file.stat().st_size
            except Exception as e:
                logger.error(f"Error calculating size for {directory}: {e}")
        
        return total_bytes / (1024 * 1024)  # Convert to MB
    
    async def manual_cleanup(self) -> Dict:
        """
        Executa limpeza manual (fora do schedule)
        
        Returns:
            Relatório de limpeza
        """
        logger.info("🧹 Manual cleanup triggered")
        return await self.run_cleanup()
