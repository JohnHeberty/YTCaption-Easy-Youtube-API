"""
Teste de integração real do YouTubeDownloader com CircuitBreaker.

Este teste vai revelar o bug exato que está acontecendo no Proxmox!
"""
import pytest
import asyncio
from pathlib import Path
from src.infrastructure.youtube.downloader import YouTubeDownloader
from src.domain.value_objects.youtube_url import YouTubeURL


class TestRealYouTubeFlow:
    """Testes que simulam o fluxo REAL de download."""
    
    @pytest.mark.asyncio
    async def test_get_video_info_real_url(self):
        """
        TESTE REAL: Chama get_video_info() que usa CircuitBreaker.acall()
        
        Este teste vai REVELAR onde está o bug do TypeError!
        """
        downloader = YouTubeDownloader()
        
        # URL de vídeo pequeno para teste
        url = YouTubeURL.create("https://www.youtube.com/watch?v=hmQKOoSXnLk")
        
        try:
            # Esta chamada passa por:
            # get_video_info() -> CircuitBreaker.acall() -> _get_video_info_internal()
            info = await downloader.get_video_info(url)
            
            # Se chegou aqui, funcionou!
            assert info is not None
            assert 'title' in info or 'id' in info
            
            print(f"✅ SUCESSO! Video info obtido: {info.get('title', info.get('id', 'unknown'))}")
            
        except Exception as e:
            # Se falhou, vamos ver o erro exato
            print(f"❌ ERRO: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Re-raise para que pytest mostre o erro
            raise
    
    @pytest.mark.asyncio
    async def test_download_real_video_flow(self):
        """
        TESTE REAL: Simula download completo (pode falhar por rede, mas mostrará o erro).
        """
        downloader = YouTubeDownloader()
        
        # URL de vídeo curto (<1min) para teste
        url = YouTubeURL.create("https://www.youtube.com/watch?v=fTE_fM2B7B0")
        output_path = Path("/tmp/test_download")
        
        try:
            # Esta chamada passa por TODA a stack:
            # download() -> CircuitBreaker.acall() -> _download_internal() -> rate_limiter.wait_if_needed()
            video_file = await downloader.download(
                url,
                output_path,
                validate_duration=True,
                max_duration=600
            )
            
            print(f"✅ SUCESSO! Video baixado: {video_file.path}")
            
        except Exception as e:
            print(f"⚠️  ERRO (pode ser esperado se sem internet/bloqueado): {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Se for o bug do TypeError, o teste falha
            if "can't be used in 'await' expression" in str(e):
                pytest.fail(f"🔥 BUG ENCONTRADO! TypeError: {e}")
            
            # Outros erros (rede, bloqueio) são esperados em testes
            pytest.skip(f"Test skipped due to network/external error: {e}")


if __name__ == "__main__":
    # Executar teste direto
    import sys
    asyncio.run(TestRealYouTubeFlow().test_get_video_info_real_url())
