"""
Testes para app.sqlite_blacklist
"""

import pytest
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from app.sqlite_blacklist import SQLiteBlacklist


@pytest.fixture
def temp_db():
    """Cria banco de dados temporário para testes"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    db_file = Path(db_path)
    if db_file.exists():
        db_file.unlink()
    
    # Remover arquivos WAL e SHM
    for suffix in ['-wal', '-shm']:
        wal_file = Path(f"{db_path}{suffix}")
        if wal_file.exists():
            wal_file.unlink()


@pytest.fixture
def blacklist(temp_db):
    """SQLiteBlacklist com banco temporário"""
    return SQLiteBlacklist(temp_db)


class TestSQLiteBlacklistInitialization:
    """Testes de inicialização"""
    
    def test_initialization(self, temp_db):
        """Testa inicialização do SQLiteBlacklist"""
        bl = SQLiteBlacklist(temp_db)
        
        assert bl.db_path == Path(temp_db)
        assert bl.db_path.exists()
    
    def test_creates_directory_if_not_exists(self, tmp_path):
        """Testa criação automática de diretório"""
        db_path = tmp_path / "subdir" / "test.db"
        bl = SQLiteBlacklist(str(db_path))
        
        assert db_path.parent.exists()
        assert db_path.exists()
    
    def test_schema_created(self, blacklist):
        """Testa que schema foi criado corretamente"""
        with blacklist._get_conn() as conn:
            # Verificar tabela existe
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='blacklist'"
            ).fetchone()
            assert result is not None
    
    def test_wal_mode_enabled(self, blacklist):
        """Testa que WAL mode está habilitado"""
        with blacklist._get_conn() as conn:
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0].lower() == 'wal'


class TestSQLiteBlacklistCRUD:
    """Testes de operações CRUD"""
    
    def test_add_video(self, blacklist):
        """Testa adicionar vídeo à blacklist"""
        blacklist.add(
            video_id='video123',
            reason='embedded_subtitles',
            confidence=0.85,
            metadata={'source': 'ocr'}
        )
        
        assert blacklist.is_blacklisted('video123')
    
    def test_is_blacklisted_false(self, blacklist):
        """Testa vídeo não blacklisted"""
        assert blacklist.is_blacklisted('video999') is False
    
    def test_is_blacklisted_true(self, blacklist):
        """Testa vídeo blacklisted"""
        blacklist.add('video456', reason='test', confidence=0.9)
        assert blacklist.is_blacklisted('video456') is True
    
    def test_get_entry(self, blacklist):
        """Testa obter entrada completa"""
        blacklist.add(
            video_id='video789',
            reason='bad_quality',
            confidence=0.75,
            metadata={'fps': 24}
        )
        
        entry = blacklist.get_entry('video789')
        
        assert entry is not None
        assert entry['video_id'] == 'video789'
        assert entry['reason'] == 'bad_quality'
        assert entry['confidence'] == 0.75
        assert entry['metadata']['fps'] == 24
        assert 'added_at' in entry
    
    def test_get_entry_not_found(self, blacklist):
        """Testa obter entrada inexistente"""
        entry = blacklist.get_entry('nonexistent')
        assert entry is None
    
    def test_remove_video(self, blacklist):
        """Testa remover vídeo da blacklist"""
        blacklist.add('video111', reason='test', confidence=0.8)
        assert blacklist.is_blacklisted('video111')
        
        removed = blacklist.remove('video111')
        assert removed is True
        assert not blacklist.is_blacklisted('video111')
    
    def test_remove_nonexistent(self, blacklist):
        """Testa remover vídeo que não existe"""
        removed = blacklist.remove('nonexistent')
        assert removed is False
    
    def test_add_overwrites_existing(self, blacklist):
        """Testa que INSERT OR REPLACE atualiza entrada existente"""
        blacklist.add('video222', reason='reason1', confidence=0.5)
        blacklist.add('video222', reason='reason2', confidence=0.9)
        
        entry = blacklist.get_entry('video222')
        assert entry['reason'] == 'reason2'
        assert entry['confidence'] == 0.9


class TestSQLiteBlacklistPermanent:
    """Testes de blacklist permanente (sem TTL)"""
    
    def test_no_expiration(self, blacklist):
        """Testa que entradas não expiram"""
        blacklist.add('video_permanent', reason='test', confidence=0.8)
        
        # Simular passagem de tempo (adicionar entrada antiga manualmente)
        with blacklist._get_conn() as conn:
            past_added = (datetime.now() - timedelta(days=365)).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO blacklist VALUES (?, ?, ?, ?, ?)",
                ('video_old', 'test', 0.5, past_added, '{}')
            )
        
        # Ambas devem estar blacklisted
        assert blacklist.is_blacklisted('video_permanent')
        assert blacklist.is_blacklisted('video_old')
    
    def test_count_includes_all(self, blacklist):
        """Testa que count() retorna todas as entradas"""
        blacklist.add('video1', reason='test', confidence=0.8)
        blacklist.add('video2', reason='test', confidence=0.9)
        
        # Adicionar entrada antiga
        with blacklist._get_conn() as conn:
            past_added = (datetime.now() - timedelta(days=365)).isoformat()
            conn.execute(
                "INSERT INTO blacklist VALUES (?, ?, ?, ?, ?)",
                ('video_old', 'test', 0.5, past_added, '{}')
            )
        
        assert blacklist.count() == 3



class TestSQLiteBlacklistConcurrency:
    """Testes de concorrência (threading)"""
    
    def test_concurrent_writes(self, blacklist):
        """Testa escritas concorrentes de múltiplas threads"""
        num_threads = 10
        videos_per_thread = 10
        errors = []
        
        def add_videos(thread_id):
            try:
                for i in range(videos_per_thread):
                    video_id = f"thread{thread_id}_video{i}"
                    blacklist.add(video_id, reason='concurrent_test', confidence=0.8)
            except Exception as e:
                errors.append(e)
        
        # Criar e iniciar threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=add_videos, args=(i,))
            threads.append(t)
            t.start()
        
        # Aguardar conclusão
        for t in threads:
            t.join()
        
        # Verificar que não houve erros
        assert len(errors) == 0
        
        # Verificar que todos vídeos foram adicionados
        expected_count = num_threads * videos_per_thread
        assert blacklist.count() == expected_count
    
    def test_concurrent_reads_and_writes(self, blacklist):
        """Testa leituras e escritas concorrentes"""
        num_iterations = 50
        errors = []
        
        def writer():
            try:
                for i in range(num_iterations):
                    blacklist.add(f'video_w{i}', reason='test', confidence=0.5)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(num_iterations):
                    blacklist.is_blacklisted(f'video_w{i % 10}')
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Iniciar threads
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Não deve haver erros de concorrência
        assert len(errors) == 0


class TestSQLiteBlacklistQueries:
    """Testes de consultas"""
    
    def test_count(self, blacklist):
        """Testa contagem de vídeos ativos"""
        assert blacklist.count() == 0
        
        blacklist.add('video1', reason='test', confidence=0.5)
        blacklist.add('video2', reason='test', confidence=0.5)
        blacklist.add('video3', reason='test', confidence=0.5)
        
        assert blacklist.count() == 3
    
    def test_list_all(self, blacklist):
        """Testa listagem de todos vídeos"""
        # Adicionar alguns vídeos
        for i in range(5):
            blacklist.add(f'video{i}', reason=f'reason{i}', confidence=0.5 + i*0.1)
        
        # Listar todos
        videos = blacklist.list_all(limit=10)
        
        assert len(videos) == 5
        assert all('video_id' in v for v in videos)
        assert all('reason' in v for v in videos)
    
    def test_list_all_pagination(self, blacklist):
        """Testa paginação"""
        # Adicionar 10 vídeos
        for i in range(10):
            blacklist.add(f'video{i:02d}', reason='test', confidence=0.5)
            time.sleep(0.01)  # Garantir ordem
        
        # Primeira página
        page1 = blacklist.list_all(limit=3, offset=0)
        assert len(page1) == 3
        
        # Segunda página
        page2 = blacklist.list_all(limit=3, offset=3)
        assert len(page2) == 3
        
        # Não deve haver duplicados
        ids_page1 = {v['video_id'] for v in page1}
        ids_page2 = {v['video_id'] for v in page2}
        assert len(ids_page1 & ids_page2) == 0


class TestSQLiteBlacklistEdgeCases:
    """Testes de casos extremos"""
    
    def test_empty_metadata(self, blacklist):
        """Testa adicionar vídeo sem metadata"""
        blacklist.add('video_no_meta', reason='test', confidence=0.5)
        entry = blacklist.get_entry('video_no_meta')
        
        assert entry is not None
        assert entry['metadata'] == {}
    
    def test_confidence_bounds(self, blacklist):
        """Testa limites de confidence"""
        # Mínimo válido
        blacklist.add('video_min', reason='test', confidence=0.0)
        assert blacklist.is_blacklisted('video_min')
        
        # Máximo válido
        blacklist.add('video_max', reason='test', confidence=1.0)
        assert blacklist.is_blacklisted('video_max')
    
    def test_invalid_confidence_rejected(self, blacklist):
        """Testa que confidence fora dos limites é rejeitada"""
        with pytest.raises(Exception):  # SQLite CHECK constraint
            blacklist.add('video_invalid', reason='test', confidence=1.5)
    
    def test_large_metadata(self, blacklist):
        """Testa metadata grande"""
        large_metadata = {
            'description': 'x' * 1000,
            'tags': list(range(100)),
            'nested': {'a': {'b': {'c': 'deep'}}}
        }
        
        blacklist.add('video_large', reason='test', confidence=0.5, metadata=large_metadata)
        entry = blacklist.get_entry('video_large')
        
        assert entry['metadata'] == large_metadata
    
    def test_special_characters_in_video_id(self, blacklist):
        """Testa caracteres especiais em video_id"""
        special_id = "video-_123.test"
        blacklist.add(special_id, reason='test', confidence=0.5)
        
        assert blacklist.is_blacklisted(special_id)
    
    def test_unicode_in_reason(self, blacklist):
        """Testa unicode em reason"""
        unicode_reason = "Legendas embutidas detectadas 日本語"
        blacklist.add('video_unicode', reason=unicode_reason, confidence=0.5)
        
        entry = blacklist.get_entry('video_unicode')
        assert entry['reason'] == unicode_reason
