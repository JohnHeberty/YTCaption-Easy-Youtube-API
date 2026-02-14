#!/usr/bin/env python3
"""
Reavaliação da Blacklist com SubtitleClassifierV2 (threshold 0.75)

Este script:
1. Carrega todos os vídeos da blacklist.db
2. Reprocessa cada um com o novo classificador V2
3. Remove da blacklist vídeos que agora são aprovados (falsos positivos corrigidos)
4. Gera relatório de recuperação

Uso:
    python reevaluate_blacklist.py
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importar VideoValidator
from app.video_validator import VideoValidator
from app.config import get_settings
import os

class BlacklistReevaluator:
    def __init__(self, db_path: str = "storage/shorts_cache/blacklist.db"):
        self.db_path = Path(db_path)
        self.settings = get_settings()
        
        # VideoValidator não precisa de settings no construtor
        # Ele usa os valores do environment/config internamente
        self.validator = VideoValidator(self.settings)
        self.results = {
            'total': 0,
            'reevaluated': 0,
            'still_blocked': 0,
            'recovered': 0,
            'errors': 0,
            'recovered_videos': [],
            'still_blocked_videos': []
        }
        
    def load_blacklist(self) -> List[Dict]:
        """Carrega todos os vídeos da blacklist"""
        if not self.db_path.exists():
            logger.error(f"Blacklist database not found: {self.db_path}")
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verificar estrutura da tabela
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Tables in database: {tables}")
        
        # Tentar diferentes estruturas possíveis
        try:
            cursor.execute("""
                SELECT video_id, reason, confidence, added_at, video_path
                FROM blocked_videos
                ORDER BY added_at DESC
            """)
        except sqlite3.OperationalError:
            try:
                cursor.execute("""
                    SELECT video_id, reason, confidence, added_at
                    FROM blacklist
                    ORDER BY added_at DESC
                """)
            except sqlite3.OperationalError:
                logger.error("Could not find blacklist table")
                conn.close()
                return []
        
        videos = []
        for row in cursor.fetchall():
            video_data = {
                'video_id': row[0],
                'reason': row[1],
                'confidence': row[2],
                'added_at': row[3]
            }
            
            # Adicionar video_path se disponível
            if len(row) > 4:
                video_data['video_path'] = row[4]
            
            videos.append(video_data)
        
        conn.close()
        
        logger.info(f"Loaded {len(videos)} videos from blacklist")
        return videos
    
    def find_video_file(self, video_id: str) -> Path:
        """Encontra o arquivo do vídeo em storage"""
        search_paths = [
            Path("storage/shorts_cache") / f"{video_id}.mp4",
            Path("storage/OK") / f"{video_id}.mp4",
            Path("storage/NOT_OK") / f"{video_id}.mp4",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def reevaluate_video(self, video_id: str, original_reason: str) -> Tuple[bool, str, float]:
        """
        Reavalia um vídeo com o novo classificador V2
        
        Returns:
            (should_block, reason, confidence)
        """
        # Encontrar arquivo
        video_path = self.find_video_file(video_id)
        
        if not video_path:
            logger.warning(f"Video file not found for {video_id}")
            return None, "video_not_found", 0.0
        
        logger.info(f"Reevaluating: {video_id} (original: {original_reason})")
        
        try:
            # Detectar com novo classificador
            has_subtitles, confidence, reason = self.validator.has_embedded_subtitles(
                str(video_path),
                timeout=60
            )
            
            return has_subtitles, reason, confidence
            
        except Exception as e:
            logger.error(f"Error processing {video_id}: {e}")
            return None, f"error: {e}", 0.0
    
    def remove_from_blacklist(self, video_id: str):
        """Remove vídeo da blacklist (falso positivo corrigido)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM blocked_videos WHERE video_id = ?", (video_id,))
        except sqlite3.OperationalError:
            cursor.execute("DELETE FROM blacklist WHERE video_id = ?", (video_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Removed {video_id} from blacklist")
    
    def run_reevaluation(self, dry_run: bool = False):
        """
        Executa reavaliação completa da blacklist
        
        Args:
            dry_run: Se True, não remove da blacklist (apenas reporta)
        """
        videos = self.load_blacklist()
        
        if not videos:
            logger.warning("No videos in blacklist to reevaluate")
            return
        
        self.results['total'] = len(videos)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 BLACKLIST REEVALUATION - TRSD V2 (threshold 0.75)")
        logger.info(f"{'='*80}\n")
        logger.info(f"Total videos to reevaluate: {len(videos)}")
        logger.info(f"Dry run mode: {dry_run}\n")
        
        for i, video in enumerate(videos, 1):
            video_id = video['video_id']
            original_reason = video['reason']
            
            logger.info(f"\n[{i}/{len(videos)}] Processing {video_id}...")
            logger.info(f"  Original reason: {original_reason}")
            
            # Reevaluar
            should_block, new_reason, confidence = self.reevaluate_video(video_id, original_reason)
            
            if should_block is None:
                # Erro ou vídeo não encontrado
                self.results['errors'] += 1
                logger.warning(f"  ⚠️ Could not reevaluate: {new_reason}")
                continue
            
            self.results['reevaluated'] += 1
            
            if should_block:
                # Ainda deve ser bloqueado (verdadeiro positivo)
                self.results['still_blocked'] += 1
                self.results['still_blocked_videos'].append({
                    'video_id': video_id,
                    'reason': new_reason,
                    'confidence': confidence
                })
                logger.info(f"  ❌ STILL BLOCKED: {new_reason} (conf={confidence:.2f})")
                
            else:
                # Não detectou legenda - FALSO POSITIVO CORRIGIDO!
                self.results['recovered'] += 1
                self.results['recovered_videos'].append({
                    'video_id': video_id,
                    'original_reason': original_reason,
                    'new_reason': new_reason
                })
                logger.info(f"  ✅ RECOVERED (false positive!): {new_reason}")
                
                if not dry_run:
                    self.remove_from_blacklist(video_id)
        
        # Relatório final
        self.print_report()
    
    def print_report(self):
        """Imprime relatório final"""
        r = self.results
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 REEVALUATION REPORT")
        logger.info(f"{'='*80}\n")
        
        logger.info(f"Total videos in blacklist:     {r['total']}")
        logger.info(f"Successfully reevaluated:      {r['reevaluated']}")
        logger.info(f"Errors:                        {r['errors']}")
        logger.info(f"")
        logger.info(f"✅ RECOVERED (false positives): {r['recovered']}")
        logger.info(f"❌ STILL BLOCKED (true pos):    {r['still_blocked']}")
        
        if r['reevaluated'] > 0:
            recovery_rate = (r['recovered'] / r['reevaluated']) * 100
            logger.info(f"\n🎯 Recovery rate: {recovery_rate:.1f}%")
            
            if r['recovered'] > 0:
                logger.info(f"\n📋 Recovered videos (now approved):")
                for video in r['recovered_videos']:
                    logger.info(f"  - {video['video_id']}")
                    logger.info(f"    Original: {video['original_reason']}")
                    logger.info(f"    New:      {video['new_reason']}")
        
        logger.info(f"\n{'='*80}\n")
        
        # Salvar relatório em arquivo
        self.save_report()
    
    def save_report(self):
        """Salva relatório em arquivo"""
        report_path = Path("storage/blacklist_reevaluation_report.txt")
        
        with open(report_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("BLACKLIST REEVALUATION REPORT - TRSD V2\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            r = self.results
            
            f.write(f"Total videos in blacklist:     {r['total']}\n")
            f.write(f"Successfully reevaluated:      {r['reevaluated']}\n")
            f.write(f"Errors:                        {r['errors']}\n\n")
            
            f.write(f"✅ RECOVERED (false positives): {r['recovered']}\n")
            f.write(f"❌ STILL BLOCKED (true pos):    {r['still_blocked']}\n\n")
            
            if r['reevaluated'] > 0:
                recovery_rate = (r['recovered'] / r['reevaluated']) * 100
                f.write(f"🎯 Recovery rate: {recovery_rate:.1f}%\n\n")
            
            if r['recovered'] > 0:
                f.write("="*80 + "\n")
                f.write("RECOVERED VIDEOS (False Positives Corrected)\n")
                f.write("="*80 + "\n\n")
                
                for video in r['recovered_videos']:
                    f.write(f"Video ID:  {video['video_id']}\n")
                    f.write(f"Original:  {video['original_reason']}\n")
                    f.write(f"New:       {video['new_reason']}\n")
                    f.write("-"*80 + "\n")
                f.write("\n")
            
            if r['still_blocked'] > 0:
                f.write("="*80 + "\n")
                f.write("STILL BLOCKED VIDEOS (True Positives)\n")
                f.write("="*80 + "\n\n")
                
                for video in r['still_blocked_videos']:
                    f.write(f"Video ID:   {video['video_id']}\n")
                    f.write(f"Reason:     {video['reason']}\n")
                    f.write(f"Confidence: {video['confidence']:.2f}\n")
                    f.write("-"*80 + "\n")
        
        logger.info(f"📄 Report saved to: {report_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reevaluate blacklist with SubtitleClassifierV2"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't remove from blacklist, just report"
    )
    parser.add_argument(
        '--db-path',
        default="storage/shorts_cache/blacklist.db",
        help="Path to blacklist database"
    )
    
    args = parser.parse_args()
    
    # Verificar se TRSD está habilitado via environment variable
    trsd_enabled = os.getenv('TRSD_ENABLED', 'false').lower() == 'true'
    
    if not trsd_enabled:
        logger.error("TRSD is not enabled! Set TRSD_ENABLED=true in .env or docker-compose.yml")
        logger.error(f"Current TRSD_ENABLED value: {os.getenv('TRSD_ENABLED')}")
        return 1
    
    logger.info("✅ TRSD V2 enabled with SubtitleClassifierV2")
    logger.info(f"   Using advanced 6-metric classification system")
    logger.info(f"   Threshold: 0.75 (optimized for 100% precision)\n")
    
    # Criar reevaluator
    reevaluator = BlacklistReevaluator(db_path=args.db_path)
    
    # Executar reavaliação
    reevaluator.run_reevaluation(dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
