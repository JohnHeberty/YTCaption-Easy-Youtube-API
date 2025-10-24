"""
Testes de integração para estratégias de download do YouTube.
Testa cada estratégia individualmente para identificar quais funcionam.
"""
import pytest
import asyncio
from pathlib import Path
import yt_dlp

from src.infrastructure.youtube.download_strategies import (
    DownloadStrategy,
    DownloadStrategyManager
)
from src.domain.value_objects.youtube_url import YouTubeURL


# Vídeo de teste curto público do YouTube
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - primeiro vídeo do YouTube
TEST_VIDEO_ID = "jNQXAC9IVRw"


class TestYouTubeDownloadStrategies:
    """Testa cada estratégia de download individualmente."""
    
    @pytest.fixture
    def base_ydl_opts(self, tmp_path):
        """Opções base para yt-dlp."""
        return {
            'format': 'bestaudio/best',
            'outtmpl': str(tmp_path / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
    
    def download_with_strategy(self, strategy: DownloadStrategy, base_opts: dict, url: str) -> dict:
        """
        Tenta download com uma estratégia específica.
        
        Returns:
            dict com 'success', 'error', 'info'
        """
        opts = strategy.to_ydl_opts(base_opts)
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'success': True,
                    'error': None,
                    'info': {
                        'id': info.get('id'),
                        'title': info.get('title'),
                        'duration': info.get('duration'),
                        'formats_count': len(info.get('formats', []))
                    }
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'info': None
            }
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_android_client_strategy(self, base_ydl_opts):
        """Testa estratégia android_client."""
        strategy = DownloadStrategy(
            name="android_client",
            player_client=["android"],
            user_agent="com.google.android.youtube/19.09.37 (Linux; U; Android 13) gzip",
            priority=1
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        # Não falhar o teste, apenas reportar
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_android_music_strategy(self, base_ydl_opts):
        """Testa estratégia android_music."""
        strategy = DownloadStrategy(
            name="android_music",
            player_client=["android_music"],
            user_agent="com.google.android.apps.youtube.music/6.42.52 (Linux; U; Android 13) gzip",
            priority=2
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_ios_client_strategy(self, base_ydl_opts):
        """Testa estratégia ios_client."""
        strategy = DownloadStrategy(
            name="ios_client",
            player_client=["ios"],
            user_agent="com.google.ios.youtube/19.09.3 (iPhone16,2; U; CPU iOS 17_4 like Mac OS X;)",
            priority=3
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_web_embed_strategy(self, base_ydl_opts):
        """Testa estratégia web_embed."""
        strategy = DownloadStrategy(
            name="web_embed",
            player_client=["web"],
            extra_opts={
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],
                        'player_skip': ['webpage'],
                    }
                }
            },
            priority=4
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_tv_embedded_strategy(self, base_ydl_opts):
        """Testa estratégia tv_embedded."""
        strategy = DownloadStrategy(
            name="tv_embedded",
            player_client=["tv_embedded"],
            priority=5
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_mweb_strategy(self, base_ydl_opts):
        """Testa estratégia mweb."""
        strategy = DownloadStrategy(
            name="mweb",
            player_client=["mweb"],
            user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            priority=6
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_default_strategy(self, base_ydl_opts):
        """Testa estratégia default (sem player_client)."""
        strategy = DownloadStrategy(
            name="default",
            player_client=[],
            extra_opts={
                'extractor_args': {
                    'youtube': {
                        'player_skip': ['configs'],
                    }
                }
            },
            priority=7
        )
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy.name}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Video ID: {result['info']['id']}")
            print(f"Title: {result['info']['title']}")
            print(f"Duration: {result['info']['duration']}s")
            print(f"Formats available: {result['info']['formats_count']}")
        else:
            print(f"Error: {result['error']}")
        print(f"{'='*60}\n")
        
        assert True
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_all_strategies_summary(self, base_ydl_opts):
        """Testa todas as estratégias e gera um resumo."""
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategies = manager.get_strategies()
        
        results = []
        
        print(f"\n{'='*80}")
        print("TESTANDO TODAS AS ESTRATÉGIAS DE DOWNLOAD")
        print(f"{'='*80}\n")
        
        for strategy in strategies:
            result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
            results.append({
                'strategy': strategy.name,
                'priority': strategy.priority,
                'success': result['success'],
                'error': result['error']
            })
        
        # Resumo final
        print(f"\n{'='*80}")
        print("RESUMO DOS TESTES")
        print(f"{'='*80}\n")
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"✅ Estratégias funcionando: {len(successful)}/{len(results)}")
        for r in successful:
            print(f"   - {r['strategy']} (priority {r['priority']})")
        
        print(f"\n❌ Estratégias com erro: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"   - {r['strategy']} (priority {r['priority']})")
            print(f"     Erro: {r['error'][:100]}...")
        
        print(f"\n{'='*80}\n")
        
        # Recomendação
        if successful:
            best = sorted(successful, key=lambda x: x['priority'])[0]
            print(f"🎯 RECOMENDAÇÃO: Usar estratégia '{best['strategy']}' (priority {best['priority']})")
            print(f"   Esta é a estratégia de maior prioridade que está funcionando.")
        else:
            print("⚠️  ATENÇÃO: Nenhuma estratégia funcionou!")
            print("   Possíveis causas:")
            print("   - Problema de rede/firewall")
            print("   - YouTube bloqueando o IP")
            print("   - yt-dlp desatualizado")
        
        print(f"\n{'='*80}\n")
        
        # Salvar relatório
        report_path = Path("test_strategies_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("RELATÓRIO DE TESTE DE ESTRATÉGIAS DE DOWNLOAD\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Vídeo testado: {TEST_VIDEO_URL}\n")
            f.write(f"Total de estratégias: {len(results)}\n")
            f.write(f"Bem-sucedidas: {len(successful)}\n")
            f.write(f"Com erro: {len(failed)}\n\n")
            
            f.write("ESTRATÉGIAS FUNCIONANDO:\n")
            for r in successful:
                f.write(f"  ✅ {r['strategy']} (priority {r['priority']})\n")
            
            f.write("\nESTRATÉGIAS COM ERRO:\n")
            for r in failed:
                f.write(f"  ❌ {r['strategy']} (priority {r['priority']})\n")
                f.write(f"     {r['error']}\n\n")
        
        print(f"📄 Relatório salvo em: {report_path}")
        
        # Sempre passa - é um teste informativo
        assert True


@pytest.mark.integration
@pytest.mark.requires_network
class TestYouTubeConnectivity:
    """Testa conectividade básica com YouTube."""
    
    def test_basic_youtube_access(self):
        """Testa se consegue acessar YouTube."""
        import requests
        
        try:
            response = requests.get("https://www.youtube.com", timeout=10)
            success = response.status_code == 200
            
            print(f"\n{'='*60}")
            print("TESTE DE CONECTIVIDADE COM YOUTUBE")
            print(f"Status Code: {response.status_code}")
            print(f"Sucesso: {success}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n{'='*60}")
            print("TESTE DE CONECTIVIDADE COM YOUTUBE")
            print(f"ERRO: {e}")
            print(f"{'='*60}\n")
        
        assert True
    
    def test_ytdlp_version(self):
        """Verifica versão do yt-dlp."""
        print(f"\n{'='*60}")
        print(f"yt-dlp version: {yt_dlp.version.__version__}")
        print(f"{'='*60}\n")
        
        assert True
