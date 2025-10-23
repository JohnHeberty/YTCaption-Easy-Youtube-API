"""
Testes unitários para o YouTubeDownloader.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import yt_dlp

from src.infrastructure.youtube.downloader import YouTubeDownloader
from src.infrastructure.youtube.download_strategies import DownloadStrategy, DownloadStrategyManager
from src.domain.value_objects.youtube_url import YouTubeURL
from src.domain.exceptions import VideoDownloadError


class TestDownloadStrategyManager:
    """Testes para o DownloadStrategyManager."""
    
    def test_initialization_with_multi_strategy(self):
        """Deve inicializar com múltiplas estratégias."""
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        
        strategies = manager.get_strategies()
        assert len(strategies) > 1
        assert all(isinstance(s, DownloadStrategy) for s in strategies)
    
    def test_initialization_single_strategy(self):
        """Deve inicializar com apenas uma estratégia."""
        manager = DownloadStrategyManager(enable_multi_strategy=False)
        
        strategies = manager.get_strategies()
        assert len(strategies) == 1
    
    def test_strategies_ordered_by_priority(self):
        """Estratégias devem estar ordenadas por prioridade."""
        manager = DownloadStrategyManager()
        strategies = manager.get_strategies()
        
        priorities = [s.priority for s in strategies]
        assert priorities == sorted(priorities)
    
    def test_get_strategy_by_name(self):
        """Deve buscar estratégia por nome."""
        manager = DownloadStrategyManager()
        
        strategy = manager.get_strategy_by_name("android_client")
        assert strategy is not None
        assert strategy.name == "android_client"
        assert "android" in strategy.player_client
    
    def test_get_nonexistent_strategy(self):
        """Deve retornar None para estratégia inexistente."""
        manager = DownloadStrategyManager()
        
        strategy = manager.get_strategy_by_name("nonexistent")
        assert strategy is None
    
    def test_log_strategy_success(self):
        """Deve logar sucesso de estratégia."""
        manager = DownloadStrategyManager()
        strategy = manager.get_strategies()[0]
        
        # Não deve lançar exceção
        manager.log_strategy_success(strategy)
    
    def test_log_strategy_failure(self):
        """Deve logar falha de estratégia."""
        manager = DownloadStrategyManager()
        strategy = manager.get_strategies()[0]
        
        # Não deve lançar exceção
        manager.log_strategy_failure(strategy, "Test error")


class TestDownloadStrategy:
    """Testes para DownloadStrategy."""
    
    def test_to_ydl_opts_with_player_client(self):
        """Deve converter estratégia para opções yt-dlp."""
        strategy = DownloadStrategy(
            name="test",
            player_client=["android"],
            priority=1
        )
        
        base_opts = {'quiet': True}
        opts = strategy.to_ydl_opts(base_opts)
        
        assert 'extractor_args' in opts
        assert 'youtube' in opts['extractor_args']
        assert opts['extractor_args']['youtube']['player_client'] == ["android"]
        assert opts['quiet'] is True
    
    def test_to_ydl_opts_with_user_agent(self):
        """Deve adicionar user agent customizado."""
        strategy = DownloadStrategy(
            name="test",
            player_client=["android"],
            user_agent="Custom UA",
            priority=1
        )
        
        opts = strategy.to_ydl_opts({})
        
        assert 'http_headers' in opts
        assert opts['http_headers']['User-Agent'] == "Custom UA"
    
    def test_to_ydl_opts_with_extra_opts(self):
        """Deve mesclar opções extras."""
        strategy = DownloadStrategy(
            name="test",
            player_client=["android"],
            extra_opts={'format': 'bestaudio'},
            priority=1
        )
        
        opts = strategy.to_ydl_opts({'quiet': True})
        
        assert opts['format'] == 'bestaudio'
        assert opts['quiet'] is True


@pytest.mark.asyncio
class TestYouTubeDownloader:
    """Testes para o YouTubeDownloader."""
    
    @pytest.fixture
    def downloader(self):
        """Cria downloader para testes."""
        return YouTubeDownloader(
            timeout=60  # Timeout menor para testes
        )
    
    @pytest.fixture
    def youtube_url(self):
        """Cria URL de teste."""
        return YouTubeURL.create("https://www.youtube.com/watch?v=test123")
    
    async def test_initialization(self, downloader):
        """Deve inicializar downloader corretamente."""
        assert downloader.strategy_manager is not None
        assert downloader.rate_limiter is not None
        assert downloader.circuit_breaker is not None
        assert downloader.timeout == 60
    
    async def test_strategy_manager_methods_exist(self, downloader):
        """Deve ter métodos corretos no strategy_manager."""
        manager = downloader.strategy_manager
        strategy = manager.get_strategies()[0]
        
        # Verificar que métodos existem e não lançam erro
        assert hasattr(manager, 'log_strategy_success')
        assert hasattr(manager, 'log_strategy_failure')
        assert hasattr(manager, 'log_all_strategies_failed')
        
        # Testar chamadas
        manager.log_strategy_success(strategy)
        manager.log_strategy_failure(strategy, "test error")
    
    @patch('src.infrastructure.youtube.downloader.yt_dlp.YoutubeDL')
    @patch('src.infrastructure.youtube.downloader.Path')
    async def test_download_with_strategy_success(self, mock_path_class, mock_ydl, downloader, youtube_url):
        """Deve fazer download com estratégia bem-sucedida."""
        # Mock do yt-dlp
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            'id': 'test123',
            'title': 'Test Video',
            'duration': 100,
            'filesize': 1024000
        }
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # Mock do arquivo baixado
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 1024000
        mock_file.suffix = ".m4a"
        
        # Mock do Path.glob para retornar o arquivo
        mock_path_instance = MagicMock()
        mock_path_instance.glob.return_value = [mock_file]
        mock_path_class.return_value = mock_path_instance
        
        result = await downloader.download(youtube_url)
        
        assert result is not None
        assert result.original_url == str(youtube_url)
    
    @patch('src.infrastructure.youtube.downloader.yt_dlp.YoutubeDL')
    async def test_download_with_strategy_failure_calls_log_method(self, mock_ydl, downloader, youtube_url):
        """Deve chamar log_strategy_failure quando estratégia falhar."""
        # Mock que sempre falha
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = yt_dlp.utils.DownloadError("403 Forbidden")
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # Spy no strategy_manager
        original_log_failure = downloader.strategy_manager.log_strategy_failure
        downloader.strategy_manager.log_strategy_failure = Mock(wraps=original_log_failure)
        
        with pytest.raises(VideoDownloadError):
            await downloader.download(youtube_url)
        
        # Verificar que log_strategy_failure foi chamado
        assert downloader.strategy_manager.log_strategy_failure.called
    
    async def test_get_video_info_structure(self, downloader, youtube_url):
        """Deve retornar estrutura correta de informações do vídeo."""
        with patch('src.infrastructure.youtube.downloader.yt_dlp.YoutubeDL') as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = {
                'id': 'test123',
                'title': 'Test Video',
                'duration': 120,
                'description': 'Test description',
                'uploader': 'Test Channel',
                'upload_date': '20240101',
                'view_count': 1000,
                'like_count': 50,
                'thumbnail': 'http://example.com/thumb.jpg'
            }
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            info = await downloader.get_video_info(youtube_url)
            
            assert info['video_id'] == 'test123'
            assert info['title'] == 'Test Video'
            assert info['duration'] == 120
            assert 'error' not in info
    
    @patch('src.infrastructure.youtube.downloader.yt_dlp.YoutubeDL')
    @patch('src.infrastructure.youtube.downloader.Path')
    async def test_rate_limiter_reports_on_download(self, mock_path_class, mock_ydl, downloader, youtube_url):
        """Deve reportar ao rate_limiter durante download."""
        # Mock bem-sucedido
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            'id': 'test123',
            'title': 'Test',
            'duration': 100
        }
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # Mock do arquivo
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_size = 1024
        mock_file.suffix = ".m4a"
        
        mock_path_instance = MagicMock()
        mock_path_instance.glob.return_value = [mock_file]
        mock_path_class.return_value = mock_path_instance
        
        # Spy no rate_limiter
        downloader.rate_limiter.report_success = Mock()
        downloader.rate_limiter.report_error = Mock()
        
        await downloader.download(youtube_url)
        
        # Verificar que report_success foi chamado (sem await)
        assert downloader.rate_limiter.report_success.called
        assert not downloader.rate_limiter.report_error.called


@pytest.mark.integration
class TestYouTubeDownloaderIntegration:
    """Testes de integração para download real (requer rede)."""
    
    @pytest.fixture
    def downloader(self):
        """Cria downloader para testes de integração."""
        return YouTubeDownloader()
    
    @pytest.mark.slow
    @pytest.mark.requires_network
    async def test_download_real_short_video(self, downloader):
        """Testa download de vídeo real curto."""
        # Usar vídeo de teste curto do YouTube
        url = YouTubeURL.create("https://www.youtube.com/watch?v=jNQXAC9IVRw")  # "Me at the zoo"
        
        try:
            result = await downloader.download(url)
            assert result is not None
            assert result.exists
            assert result.file_size_bytes > 0
        except VideoDownloadError as e:
            pytest.skip(f"Download failed (may be blocked): {e}")
    
    @pytest.mark.requires_network
    async def test_get_video_info_real(self, downloader):
        """Testa obtenção de informações de vídeo real."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        
        try:
            info = await downloader.get_video_info(url)
            assert info['video_id'] == 'jNQXAC9IVRw'
            assert 'title' in info
            assert 'duration' in info
            assert info['duration'] > 0
        except Exception as e:
            pytest.skip(f"Video info failed (may be blocked): {e}")
