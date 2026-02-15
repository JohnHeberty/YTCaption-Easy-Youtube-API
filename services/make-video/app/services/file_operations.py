"""
File Operations Module
Gerencia movimentação de arquivos entre stages do pipeline

REGRA FUNDAMENTAL: MOVER, NÃO COPIAR
- Arquivos são MOVIDOS entre pastas (não copiados)
- Economiza espaço em disco
- Evita duplicação
- Garante single source of truth

Flow de arquivos:
1. download → data/raw/shorts/{video_id}.mp4
2. transform → data/transform/videos/{video_id}.mp4 (MOVE de raw/)
3. approval → data/approved/videos/{video_id}.mp4 (MOVE de transform/)
4. rejection → DELETE arquivo + registro no DB

Tracking:
- Cada movimentação é registrada no VideoStatusStore
- File path atualizado no banco
- Histórico completo de transições
"""

import shutil
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class FileOperations:
    """
    Gerencia movimentação segura de arquivos no pipeline
    
    Princípios:
    - Move (não copia) para economizar disco
    - Atualiza tracking no banco
    - Rollback em caso de erro
    - Validação de integridade
    """
    
    def __init__(self, data_dir: str = "./data"):
        """
        Args:
            data_dir: Diretório raiz dos dados
        """
        self.data_dir = Path(data_dir)
        
        # Diretórios do pipeline
        self.raw_dir = self.data_dir / "raw" / "shorts"
        self.transform_dir = self.data_dir / "transform" / "videos"
        self.approved_dir = self.data_dir / "approved" / "videos"
        
        # Criar dirs se não existirem
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.transform_dir.mkdir(parents=True, exist_ok=True)
        self.approved_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug("FileOperations initialized")
    
    def move_to_transform(self, video_id: str, source_path: Optional[Path] = None) -> Path:
        """
        Move vídeo de raw/ para transform/
        
        Args:
            video_id: ID do vídeo
            source_path: Caminho origem (default: raw/{video_id}.mp4)
        
        Returns:
            Novo caminho do arquivo em transform/
        
        Raises:
            FileNotFoundError: Se arquivo origem não existir
            IOError: Se movimentação falhar
        """
        if source_path is None:
            source_path = self.raw_dir / f"{video_id}.mp4"
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        dest_path = self.transform_dir / f"{video_id}.mp4"
        
        try:
            # Remover destino se já existir (edge case)
            if dest_path.exists():
                logger.warning(f"Destination already exists, removing: {dest_path}")
                dest_path.unlink()
            
            # MOVER (não copiar)
            shutil.move(str(source_path), str(dest_path))
            
            # Validar movimentação
            if not dest_path.exists():
                raise IOError(f"Move failed: {dest_path} not created")
            
            if source_path.exists():
                raise IOError(f"Move failed: {source_path} still exists")
            
            logger.info(f"📦 MOVED: {source_path.name} → transform/")
            return dest_path
            
        except Exception as e:
            logger.error(f"Failed to move {video_id} to transform: {e}")
            # Rollback: garantir que arquivo está em raw/
            if not source_path.exists() and dest_path.exists():
                shutil.move(str(dest_path), str(source_path))
                logger.info(f"Rollback: restored {source_path}")
            raise
    
    def move_to_approved(self, video_id: str, source_path: Optional[Path] = None) -> Path:
        """
        Move vídeo de transform/ para approved/
        
        Args:
            video_id: ID do vídeo
            source_path: Caminho origem (default: transform/{video_id}.mp4)
        
        Returns:
            Novo caminho do arquivo em approved/
        
        Raises:
            FileNotFoundError: Se arquivo origem não existir
            IOError: Se movimentação falhar
        """
        if source_path is None:
            source_path = self.transform_dir / f"{video_id}.mp4"
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        dest_path = self.approved_dir / f"{video_id}.mp4"
        
        try:
            # Remover destino se já existir
            if dest_path.exists():
                logger.warning(f"Destination already exists, removing: {dest_path}")
                dest_path.unlink()
            
            # MOVER (não copiar)
            shutil.move(str(source_path), str(dest_path))
            
            # Validar movimentação
            if not dest_path.exists():
                raise IOError(f"Move failed: {dest_path} not created")
            
            if source_path.exists():
                raise IOError(f"Move failed: {source_path} still exists")
            
            logger.info(f"✅ MOVED: {source_path.name} → approved/")
            return dest_path
            
        except Exception as e:
            logger.error(f"Failed to move {video_id} to approved: {e}")
            # Rollback
            if not source_path.exists() and dest_path.exists():
                shutil.move(str(dest_path), str(source_path))
                logger.info(f"Rollback: restored {source_path}")
            raise
    
    def delete_rejected(self, video_id: str, source_path: Optional[Path] = None):
        """
        Remove arquivo de vídeo rejeitado
        
        Args:
            video_id: ID do vídeo
            source_path: Caminho do arquivo (pode estar em qualquer stage)
        """
        if source_path is None:
            # Tentar encontrar em qualquer pasta
            possible_paths = [
                self.raw_dir / f"{video_id}.mp4",
                self.transform_dir / f"{video_id}.mp4",
                self.approved_dir / f"{video_id}.mp4"
            ]
            
            source_path = next((p for p in possible_paths if p.exists()), None)
            
            if source_path is None:
                logger.warning(f"Rejected file not found (already deleted?): {video_id}")
                return
        
        try:
            if source_path.exists():
                source_path.unlink()
                logger.info(f"🗑️  DELETED rejected: {source_path}")
            else:
                logger.warning(f"File not found for deletion: {source_path}")
                
        except Exception as e:
            logger.error(f"Failed to delete rejected {video_id}: {e}")
            raise
    
    def find_file(self, video_id: str) -> Optional[Path]:
        """
        Encontra arquivo em qualquer stage do pipeline
        
        Args:
            video_id: ID do vídeo
        
        Returns:
            Path do arquivo ou None se não encontrado
        """
        possible_paths = [
            self.raw_dir / f"{video_id}.mp4",
            self.transform_dir / f"{video_id}.mp4",
            self.approved_dir / f"{video_id}.mp4"
        ]
        
        return next((p for p in possible_paths if p.exists()), None)
    
    def get_file_info(self, file_path: Path) -> Dict:
        """
        Retorna informações sobre um arquivo
        
        Args:
            file_path: Caminho do arquivo
        
        Returns:
            Dicionário com metadados
        """
        if not file_path.exists():
            return {"exists": False}
        
        stat = file_path.stat()
        
        return {
            "exists": True,
            "path": str(file_path),
            "size_mb": stat.st_size / (1024 * 1024),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "stage": self._detect_stage(file_path)
        }
    
    def _detect_stage(self, file_path: Path) -> str:
        """Detecta em qual stage o arquivo está"""
        path_str = str(file_path)
        
        if str(self.raw_dir) in path_str:
            return "raw"
        elif str(self.transform_dir) in path_str:
            return "transform"
        elif str(self.approved_dir) in path_str:
            return "approved"
        else:
            return "unknown"
