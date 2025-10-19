"""
Gerenciador de sessões temporárias para transcrições paralelas.
Cada requisição cria uma pasta isolada em temp/{session_id}/ com:
- Download do vídeo
- Chunks de áudio
- Resultados parciais
Cleanup automático após processamento.
"""
from pathlib import Path
from typing import Optional, Dict
import shutil
import json
import time
import uuid
from datetime import datetime

from loguru import logger


def generate_session_id(request_ip: Optional[str] = None) -> str:
    """
    Gera ID único para sessão de transcrição.
    
    Formato: session_{timestamp}_{uuid}_{ip_hash}
    Exemplo: session_20250119_143052_a1b2c3d4_192168001100
    
    Args:
        request_ip: IP do cliente (opcional, para tracking)
        
    Returns:
        Session ID único
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]  # microseconds para unicidade
    session_uuid = uuid.uuid4().hex[:8]
    
    ip_suffix = ""
    if request_ip:
        # Hash do IP para evitar PII nos nomes de pasta
        ip_clean = request_ip.replace(".", "").replace(":", "").replace("-", "")[:12]
        ip_suffix = f"_{ip_clean}"
    
    return f"session_{timestamp}_{session_uuid}{ip_suffix}"


class TempSessionManager:
    """
    Gerencia pastas temporárias isoladas por sessão de transcrição.
    
    Estrutura criada:
    temp/
    ├── session_ID1/
    │   ├── metadata.json          # Info da request
    │   ├── download/               # Vídeo/áudio original
    │   │   └── video.mp4
    │   ├── chunks/                 # Chunks de áudio
    │   │   ├── chunk_000.wav
    │   │   ├── chunk_001.wav
    │   │   └── chunk_NNN.wav
    │   └── results/                # Resultados parciais
    │       ├── chunk_000_result.json
    │       └── chunk_001_result.json
    └── session_ID2/                # Outra requisição simultânea
        └── ...
    """
    
    def __init__(self, base_temp_dir: Path):
        """
        Inicializa gerenciador de sessões.
        
        Args:
            base_temp_dir: Diretório base para todas as sessões (ex: ./temp)
        """
        self.base_temp_dir = Path(base_temp_dir)
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Session manager initialized: base_dir={self.base_temp_dir}")
    
    def create_session_dir(
        self,
        session_id: str,
        metadata: Optional[Dict] = None
    ) -> Path:
        """
        Cria diretório isolado para a sessão com subpastas.
        
        Args:
            session_id: ID único da sessão
            metadata: Metadados opcionais (URL, IP, timestamp, etc)
            
        Returns:
            Path do diretório da sessão criado
        """
        session_dir = self.base_temp_dir / session_id
        
        # Criar estrutura de pastas
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "download").mkdir(exist_ok=True)
        (session_dir / "chunks").mkdir(exist_ok=True)
        (session_dir / "results").mkdir(exist_ok=True)
        
        # Salvar metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "base_dir": str(session_dir)
        })
        
        metadata_path = session_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created session directory: {session_id}")
        return session_dir
    
    def get_session_dir(self, session_id: str) -> Path:
        """Retorna Path do diretório da sessão."""
        return self.base_temp_dir / session_id
    
    def get_download_dir(self, session_id: str) -> Path:
        """Retorna Path do diretório de download da sessão."""
        return self.get_session_dir(session_id) / "download"
    
    def get_chunks_dir(self, session_id: str) -> Path:
        """Retorna Path do diretório de chunks da sessão."""
        return self.get_session_dir(session_id) / "chunks"
    
    def get_results_dir(self, session_id: str) -> Path:
        """Retorna Path do diretório de resultados da sessão."""
        return self.get_session_dir(session_id) / "results"
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        Remove completamente a pasta da sessão após processamento.
        
        Args:
            session_id: ID da sessão a limpar
            
        Returns:
            True se limpeza foi bem sucedida
        """
        session_dir = self.get_session_dir(session_id)
        
        if not session_dir.exists():
            logger.warning(f"Session dir not found for cleanup: {session_id}")
            return False
        
        try:
            # Remover toda a árvore de diretórios
            shutil.rmtree(session_dir)
            logger.info(f"Cleaned up session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
            return False
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Remove sessões antigas (cleanup automático periódico).
        
        Args:
            max_age_hours: Idade máxima em horas (default: 24h)
            
        Returns:
            Número de sessões removidas
        """
        current_time = time.time()
        cleaned_count = 0
        
        for session_dir in self.base_temp_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            # Ignorar diretórios que não são sessões
            if not session_dir.name.startswith("session_"):
                continue
            
            # Verificar idade da pasta
            try:
                dir_age_hours = (current_time - session_dir.stat().st_mtime) / 3600
                
                if dir_age_hours > max_age_hours:
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
                    logger.info(f"Cleaned up old session: {session_dir.name} (age: {dir_age_hours:.1f}h)")
            except Exception as e:
                logger.error(f"Failed to cleanup old session {session_dir.name}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Automatic cleanup: removed {cleaned_count} old sessions")
        
        return cleaned_count
    
    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        """
        Lê metadados da sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Dict com metadados ou None se não encontrado
        """
        metadata_path = self.get_session_dir(session_id) / "metadata.json"
        
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata for {session_id}: {e}")
            return None
    
    def list_active_sessions(self) -> list[str]:
        """
        Lista todas as sessões ativas (pastas existentes).
        
        Returns:
            Lista de session IDs ativos
        """
        active_sessions = []
        
        for session_dir in self.base_temp_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                active_sessions.append(session_dir.name)
        
        return active_sessions
    
    def get_session_size(self, session_id: str) -> int:
        """
        Calcula tamanho total em bytes da sessão.
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Tamanho total em bytes
        """
        session_dir = self.get_session_dir(session_id)
        
        if not session_dir.exists():
            return 0
        
        total_size = 0
        for item in session_dir.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
        
        return total_size
