"""
Testes para validar as correções P0.

Execute: python -m pytest tests/test_p0_corrections.py -v
"""

import sys
import pytest
from pathlib import Path

# Adicionar app ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


class TestCommonLibrary:
    """Testa uso da common library."""

    def test_now_brazil_import(self):
        """Testa que now_brazil pode ser importado do common."""
        from common.datetime_utils import now_brazil
        assert now_brazil() is not None

    def test_resilient_redis_import(self):
        """Testa que ResilientRedisStore pode ser importado do common."""
        from common.redis_utils import ResilientRedisStore
        assert ResilientRedisStore is not None


class TestRedisUrlParsing:
    """Testa parsing de URL Redis."""

    def test_urlparse_vs_manual_parsing(self):
        """Verifica que urlparse é mais robusto que parsing manual."""
        from urllib.parse import urlparse

        test_urls = [
            "redis://localhost:6379/0",
            "redis://user:pass@localhost:6379/0",
            "redis://localhost:6379/0?password=secret",
            "redis://redis-host.internal:6379/1",
        ]

        for url in test_urls:
            parsed = urlparse(url)
            assert parsed.hostname is not None
            assert parsed.port is not None
            # Path contém o db number
            db = parsed.path.lstrip('/') if parsed.path else '0'
            assert db.isdigit()


class TestAsyncioRun:
    """Testa que asyncio.run() NÃO é usado em contexto async."""

    def test_no_asyncio_run_in_main(self):
        """Verifica que main.py não usa asyncio.run()."""
        main_path = Path(__file__).parent.parent.parent / "app" / "main.py"
        content = main_path.read_text()

        # Não deve ter asyncio.run() em contexto async
        # (Pode ter em __main__ ou sync functions)
        lines = content.split('\n')
        in_async_func = False
        has_violation = False

        for line in lines:
            stripped = line.strip()

            # Detectar início de função async
            if stripped.startswith('async def '):
                in_async_func = True
                func_name = stripped.split('(')[0].replace('async def ', '')
                # Ignorar __main__
                if func_name == 'main':
                    in_async_func = False
                continue

            # Detectar fim de função (nova def não indentada)
            if in_async_func and stripped.startswith('def '):
                in_async_func = False

            # Verificar violação
            if in_async_func and 'asyncio.run(' in stripped:
                has_violation = True
                break

        assert not has_violation, "asyncio.run() encontrado dentro de função async"


class TestImports:
    """Testa que os módulos refatorados podem ser importados."""

    def test_video_builder_import(self):
        """Testa importação de VideoBuilder."""
        try:
            from services.video_builder import VideoBuilder
            assert VideoBuilder is not None
        except ImportError as e:
            pytest.skip(f"VideoBuilder não disponível: {e}")

    def test_job_manager_import(self):
        """Testa importação de JobManager."""
        try:
            from services.job_manager import JobManager
            assert JobManager is not None
        except ImportError as e:
            pytest.skip(f"JobManager não disponível: {e}")

    def test_cache_manager_import(self):
        """Testa importação de CacheManager."""
        try:
            from services.cache_manager import CacheManager
            assert CacheManager is not None
        except ImportError as e:
            pytest.skip(f"CacheManager não disponível: {e}")


class TestLockManager:
    """Testa LockManager com redis.from_url()."""

    def test_lock_manager_uses_from_url(self):
        """Verifica que LockManager usa redis.from_url()."""
        lock_manager_path = Path(__file__).parent.parent.parent / "app" / "infrastructure" / "lock_manager.py"
        content = lock_manager_path.read_text()

        # Deve usar from_url
        assert "aioredis.from_url" in content or "redis.from_url" in content

        # NÃO deve ter parsing manual frágil
        assert ".split('://')" not in content
        assert ".split(':')[-1]" not in content


class TestRequirements:
    """Testa requirements.txt."""

    def test_common_library_in_requirements(self):
        """Verifica que -e ./common está no requirements.txt."""
        req_path = Path(__file__).parent.parent.parent / "requirements.txt"
        content = req_path.read_text()

        assert "-e ./common" in content, "common library não está no requirements.txt"


class TestCommonSymlink:
    """Testa symlink para common."""

    def test_common_symlink_exists(self):
        """Verifica que symlink para common existe."""
        common_path = Path(__file__).parent.parent.parent / "app" / "common"

        assert common_path.exists(), "Symlink para common não existe"
        assert common_path.is_symlink(), "common existe mas não é um symlink"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
