"""
SQLite Blacklist Manager
Gerencia lista negra de vídeos com legendas embutidas usando SQLite
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional, Dict, List
from common.log_utils import get_logger

logger = get_logger(__name__)

class SQLiteBlacklist:
    """
    Gerencia blacklist de vídeos usando SQLite com WAL mode
    
    Features:
    - Transações ACID
    - Concorrência nativa (WAL mode)
    - Blacklist permanente (sem TTL)
    - Interface compatível com ShortsBlacklist
    """
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: Caminho do arquivo de banco de dados SQLite
        """
        self.db_path = Path(db_path)
        
        # Criar diretório se não existir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Inicializar schema
        self._init_schema()
        
        logger.info(f"✅ SQLiteBlacklist initialized: {self.db_path}")
    
    def _init_schema(self):
        """Cria schema se não existir"""
        with self._get_conn() as conn:
            self._ensure_schema(conn)

            logger.debug("Schema initialized successfully")
    
    @contextmanager
    def _get_conn(self):
        """Context manager para conexões SQLite"""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            # Se o arquivo for recriado durante runtime, garante schema antes de uso
            self._ensure_schema(conn)
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _ensure_schema(self, conn):
        """Garante que pragmas e tabela existam (idempotente)"""
        # Habilitar WAL mode (write-ahead logging)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")

        # Tabela principal
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                video_id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                added_at TIMESTAMP DEFAULT (datetime('now')),
                metadata JSON
            )
            """
        )
    
    def add(self, video_id: str, reason: str, confidence: float, metadata: Optional[Dict] = None):
        """
        Adiciona vídeo à blacklist permanentemente
        
        Args:
            video_id: ID do vídeo
            reason: Motivo (ex: "embedded_subtitles")
            confidence: Score de confiança (0-1)
            metadata: Dados adicionais opcionais
        """
        metadata_json = json.dumps(metadata or {})
        
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO blacklist VALUES (?, ?, ?, datetime('now'), ?)",
                (video_id, reason, confidence, metadata_json)
            )
        
        logger.info(f"🚫 Blacklisted: {video_id} ({reason}, conf: {confidence:.2f})")
    
    def is_blacklisted(self, video_id: str) -> bool:
        """
        Verifica se vídeo está na blacklist
        
        Args:
            video_id: ID do vídeo
            
        Returns:
            True se vídeo está na blacklist
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM blacklist WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            return row is not None
    
    def get_entry(self, video_id: str) -> Optional[Dict]:
        """
        Retorna entrada completa da blacklist
        
        Args:
            video_id: ID do vídeo
            
        Returns:
            Dicionário com dados do vídeo ou None se não encontrado
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM blacklist WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                "video_id": row["video_id"],
                "reason": row["reason"],
                "confidence": row["confidence"],
                "added_at": row["added_at"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }
    
    def remove(self, video_id: str) -> bool:
        """
        Remove vídeo da blacklist
        
        Args:
            video_id: ID do vídeo
            
        Returns:
            True se vídeo foi removido, False se não estava na blacklist
        """
        with self._get_conn() as conn:
            result = conn.execute(
                "DELETE FROM blacklist WHERE video_id = ?",
                (video_id,)
            )
            removed = result.rowcount > 0
            
            if removed:
                logger.info(f"✅ Removed from blacklist: {video_id}")
            
            return removed
    
    def count(self) -> int:
        """
        Retorna número total de vídeos na blacklist
        
        Returns:
            Contagem total de entradas
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM blacklist"
            ).fetchone()
            return row["count"]
    
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Lista todos vídeos na blacklist
        
        Args:
            limit: Número máximo de resultados
            offset: Offset para paginação
            
        Returns:
            Lista de dicionários com dados dos vídeos
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM blacklist 
                ORDER BY added_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
            
            return [
                {
                    "video_id": row["video_id"],
                    "reason": row["reason"],
                    "confidence": row["confidence"],
                    "added_at": row["added_at"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                for row in rows
            ]
