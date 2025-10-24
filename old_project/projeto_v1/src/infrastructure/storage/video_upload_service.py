"""
Serviço de upload de vídeos.
Gerencia salvamento e processamento de uploads.
"""
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from loguru import logger

from src.domain.interfaces import IStorageService
from src.domain.value_objects import UploadedVideoFile
from src.domain.exceptions import StorageError


class VideoUploadService:
    """Serviço para gerenciar uploads de vídeo."""
    
    def __init__(self, storage_service: IStorageService, chunk_size: int = 8192):
        self.storage = storage_service
        self.chunk_size = chunk_size
    
    async def save_upload(
        self,
        upload_file: UploadFile,
        temp_dir: Optional[Path] = None
    ) -> UploadedVideoFile:
        """
        Salva arquivo enviado no storage temporário.
        
        Args:
            upload_file: Arquivo FastAPI UploadFile
            temp_dir: Diretório temporário (cria se None)
            
        Returns:
            UploadedVideoFile com informações do arquivo salvo
        """
        try:
            if temp_dir is None:
                temp_dir = await self.storage.create_temp_directory()
            
            safe_filename = self._sanitize_filename(upload_file.filename)
            file_path = temp_dir / safe_filename
            
            logger.info(f"Saving upload: {safe_filename}")
            
            # Salvar em chunks (streaming)
            total_bytes = 0
            with open(file_path, 'wb') as f:
                while chunk := await upload_file.read(self.chunk_size):
                    f.write(chunk)
                    total_bytes += len(chunk)
            
            logger.info(f"✅ Upload saved: {safe_filename} ({total_bytes} bytes)")
            
            return UploadedVideoFile(
                file_path=file_path,
                original_filename=upload_file.filename,
                mime_type=upload_file.content_type or 'application/octet-stream',
                size_bytes=total_bytes
            )
            
        except Exception as e:
            logger.error(f"Failed to save upload: {str(e)}")
            raise StorageError(f"Failed to save uploaded file: {str(e)}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitiza nome do arquivo para prevenir path traversal."""
        safe_name = filename.replace('/', '_').replace('\\', '_')
        dangerous_chars = ['..', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            safe_name = safe_name.replace(char, '_')
        
        if '.' not in safe_name:
            safe_name += '.unknown'
        
        return safe_name
