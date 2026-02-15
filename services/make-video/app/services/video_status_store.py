"""
Video Status Store
Gerencia histórico completo de vídeos aprovados e reprovados usando SQLite

MUDANÇA ARQUITETURAL:
- Antes: Apenas blacklist (reprovados) 
- Agora: Approved + Rejected (histórico completo)
- Localização: data/database/video_status.db (antes: data/raw/shorts/blacklist.db)

Benefícios:
- Histórico persistente de aprovações
- Recuperação de aprovados se perder arquivos MP4
- Auditoria completa do pipeline
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class VideoStatusStore:
    """
    Gerencia status de vídeos (aprovados + reprovados) usando SQLite
    
    Tabelas:
    - approved_videos: Vídeos aprovados (sem legendas)
    - rejected_videos: Vídeos reprovados (com legendas ou outros problemas)
    
    Features:
    - Transações ACID
    - Concorrência nativa (WAL mode)
    - Histórico permanente
    - Recuperação de aprovados
    """
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: Caminho do arquivo SQLite (ex: data/database/video_status.db)
        """
        self.db_path = Path(db_path)
        
        # Criar diretório se não existir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Inicializar schema
        self._init_schema()
        
        logger.info(f"✅ VideoStatusStore initialized: {self.db_path}")
    
    def _init_schema(self):
        """Cria schema se não existir"""
        with self._get_conn() as conn:
            self._ensure_schema(conn)
            logger.debug("Schema initialized successfully")
    
    @contextmanager
    def _get_conn(self):
        """Context manager para conexões SQLite"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
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
        """Garante que pragmas e tabelas existam (idempotente)"""
        # Habilitar WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        # Tabela de vídeos APROVADOS
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approved_videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                approved_at TIMESTAMP DEFAULT (datetime('now')),
                file_path TEXT,
                metadata JSON
            )
            """
        )
        
        # Tabela de vídeos REPROVADOS
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rejected_videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                rejected_at TIMESTAMP DEFAULT (datetime('now')),
                rejection_reason TEXT NOT NULL,
                confidence REAL CHECK(confidence >= 0 AND confidence <= 1),
                metadata JSON
            )
            """
        )
        
        # Índices para performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_approved_date ON approved_videos(approved_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rejected_date ON rejected_videos(rejected_at)")
    
    # ============================================================================
    # APPROVED VIDEOS
    # ============================================================================
    
    def add_approved(self, video_id: str, title: str = None, url: str = None, 
                     file_path: str = None, metadata: Optional[Dict] = None):
        """
        Adiciona vídeo à lista de aprovados
        
        Args:
            video_id: ID do vídeo
            title: Título do vídeo (opcional)
            url: URL do vídeo (opcional)
            file_path: Caminho do arquivo MP4 aprovado
            metadata: Dados adicionais
        """
        metadata_json = json.dumps(metadata or {})
        
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approved_videos 
                (video_id, title, url, approved_at, file_path, metadata)
                VALUES (?, ?, ?, datetime('now'), ?, ?)
                """,
                (video_id, title, url, file_path, metadata_json)
            )
        
        logger.info(f"✅ APPROVED: {video_id} → {file_path}")
    
    def is_approved(self, video_id: str) -> bool:
        """Verifica se vídeo já foi aprovado anteriormente"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM approved_videos WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            return row is not None
    
    def get_approved(self, video_id: str) -> Optional[Dict]:
        """Retorna dados completos de um vídeo aprovado"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM approved_videos WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                "video_id": row["video_id"],
                "title": row["title"],
                "url": row["url"],
                "approved_at": row["approved_at"],
                "file_path": row["file_path"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }
    
    def list_approved(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Lista todos os vídeos aprovados"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approved_videos 
                ORDER BY approved_at DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
            
            return [
                {
                    "video_id": row["video_id"],
                    "title": row["title"],
                    "url": row["url"],
                    "approved_at": row["approved_at"],
                    "file_path": row["file_path"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                for row in rows
            ]
    
    def count_approved(self) -> int:
        """Conta total de vídeos aprovados"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM approved_videos").fetchone()
            return row["count"] if row else 0
    
    # ============================================================================
    # REJECTED VIDEOS
    # ============================================================================
    
    def add_rejected(self, video_id: str, reason: str, confidence: float,
                     title: str = None, url: str = None, metadata: Optional[Dict] = None):
        """
        Adiciona vídeo à lista de reprovados
        
        Args:
            video_id: ID do vídeo
            reason: Motivo da reprovação (ex: "embedded_subtitles")
            confidence: Score de confiança da detecção (0-1)
            title: Título do vídeo (opcional)
            url: URL do vídeo (opcional)
            metadata: Dados adicionais
        """
        metadata_json = json.dumps(metadata or {})
        
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rejected_videos 
                (video_id, title, url, rejected_at, rejection_reason, confidence, metadata)
                VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
                """,
                (video_id, title, url, reason, confidence, metadata_json)
            )
        
        logger.info(f"❌ REJECTED: {video_id} ({reason}, conf: {confidence:.2f})")
    
    def is_rejected(self, video_id: str) -> bool:
        """Verifica se vídeo já foi reprovado anteriormente"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM rejected_videos WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            return row is not None
    
    def get_rejected(self, video_id: str) -> Optional[Dict]:
        """Retorna dados completos de um vídeo reprovado"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM rejected_videos WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return {
                "video_id": row["video_id"],
                "title": row["title"],
                "url": row["url"],
                "rejected_at": row["rejected_at"],
                "rejection_reason": row["rejection_reason"],
                "confidence": row["confidence"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
            }
    
    def list_rejected(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Lista todos os vídeos reprovados"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM rejected_videos 
                ORDER BY rejected_at DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
            
            return [
                {
                    "video_id": row["video_id"],
                    "title": row["title"],
                    "url": row["url"],
                    "rejected_at": row["rejected_at"],
                    "rejection_reason": row["rejection_reason"],
                    "confidence": row["confidence"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                for row in rows
            ]
    
    def count_rejected(self) -> int:
        """Conta total de vídeos reprovados"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM rejected_videos").fetchone()
            return row["count"] if row else 0
    
    # ============================================================================
    # COMPATIBILIDADE COM BLACKLIST (LEGACY)
    # ============================================================================
    
    def is_blacklisted(self, video_id: str) -> bool:
        """
        Compatibilidade com código legado que usa is_blacklisted()
        Verifica se vídeo está reprovado
        """
        return self.is_rejected(video_id)
    
    def add(self, video_id: str, reason: str, confidence: float, metadata: Optional[Dict] = None):
        """
        Compatibilidade com código legado que usa add()
        Adiciona à lista de reprovados
        """
        self.add_rejected(video_id, reason, confidence, metadata=metadata)
    
    # ============================================================================
    # ESTATÍSTICAS E UTILIDADES
    # ============================================================================
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas gerais do banco"""
        return {
            "approved_count": self.count_approved(),
            "rejected_count": self.count_rejected(),
            "total_processed": self.count_approved() + self.count_rejected(),
            "approval_rate": self.count_approved() / max(1, self.count_approved() + self.count_rejected())
        }
    
    def clear_approved(self):
        """CUIDADO: Limpa TODOS os vídeos aprovados"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM approved_videos")
        logger.warning("⚠️  ALL approved videos cleared from database")
    
    def clear_rejected(self):
        """CUIDADO: Limpa TODOS os vídeos reprovados"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM rejected_videos")
        logger.warning("⚠️  ALL rejected videos cleared from database")
    
    def clear_all(self):
        """CUIDADO: Limpa TODO o banco de dados"""
        self.clear_approved()
        self.clear_rejected()
        logger.warning("⚠️  ALL video status data cleared")
