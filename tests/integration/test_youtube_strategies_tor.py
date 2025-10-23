"""
Testes de estratégias de download do YouTube usando rede Tor.

Este módulo testa cada estratégia de download individualmente
através da rede Tor para verificar se o proxy ajuda a contornar
bloqueios e restrições do YouTube.

Estratégias testadas:
1. android_client (prioridade 1)
2. android_music (prioridade 2)
3. ios_client (prioridade 3)
4. web_embed (prioridade 4)
5. tv_embedded (prioridade 5)
6. mweb (prioridade 6)
7. default (prioridade 7)
"""
import pytest
import yt_dlp
from pathlib import Path
import json
import requests
from datetime import datetime

from src.infrastructure.youtube.download_strategies import DownloadStrategyManager
from src.infrastructure.youtube.proxy_manager import get_proxy_manager


# Vídeo de teste: "Me at the zoo" - primeiro vídeo do YouTube (18 segundos)
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
TEST_VIDEO_ID = "jNQXAC9IVRw"

# Configuração do proxy Tor
TOR_PROXY_URL = "socks5://localhost:9050"  # Porta padrão do Tor
TOR_HTTP_PROXY = "http://localhost:8118"   # Porta HTTP do Tor (Polipo/Privoxy)


@pytest.fixture
def base_ydl_opts():
    """Opções base do yt-dlp para testes."""
    return {
        'format': 'worst',
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'skip_download': True,  # Não baixar, apenas testar extração
        'socket_timeout': 30,
        'retries': 2,
    }


@pytest.fixture
def tor_proxy_url():
    """URL do proxy Tor para testes."""
    return TOR_PROXY_URL


class TestTorConnectivity:
    """Testes de conectividade e configuração do Tor."""
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_tor_service_available(self):
        """Verifica se o serviço Tor está rodando."""
        print("\n" + "="*80)
        print("TESTE: Verificando se Tor está disponível")
        print("="*80)
        
        try:
            # Testar SOCKS5 proxy
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 9050))
            sock.close()
            
            if result == 0:
                print("✅ Tor SOCKS5 proxy está RODANDO na porta 9050")
                tor_available = True
            else:
                print("❌ Tor SOCKS5 proxy NÃO está rodando na porta 9050")
                print("   Execute: docker compose up -d tor-proxy")
                tor_available = False
                
        except Exception as e:
            print(f"❌ Erro ao verificar Tor: {e}")
            tor_available = False
        
        print("="*80)
        return tor_available
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_tor_ip_different(self):
        """Verifica se o IP através do Tor é diferente do IP direto."""
        print("\n" + "="*80)
        print("TESTE: Verificando mudança de IP através do Tor")
        print("="*80)
        
        try:
            # IP sem Tor
            response_direct = requests.get('https://api.ipify.org?format=json', timeout=10)
            ip_direct = response_direct.json()['ip']
            print(f"🌐 IP Direto: {ip_direct}")
            
            # IP com Tor
            proxies = {
                'http': TOR_HTTP_PROXY,
                'https': TOR_HTTP_PROXY
            }
            response_tor = requests.get('https://api.ipify.org?format=json', 
                                       proxies=proxies, timeout=30)
            ip_tor = response_tor.json()['ip']
            print(f"🧅 IP via Tor: {ip_tor}")
            
            if ip_direct != ip_tor:
                print(f"✅ IPs são DIFERENTES - Tor está funcionando!")
            else:
                print(f"⚠️ IPs são IGUAIS - Tor pode não estar roteando corretamente")
                
        except Exception as e:
            print(f"❌ Erro ao verificar IPs: {e}")
            print("   Certifique-se de que tor-proxy está rodando")
        
        print("="*80)


class TestYouTubeDownloadStrategiesWithTor:
    """Testa cada estratégia de download usando rede Tor."""
    
    def download_with_strategy(self, strategy, base_opts, url, use_tor=True):
        """
        Helper para testar download com uma estratégia específica.
        
        Args:
            strategy: Estratégia de download
            base_opts: Opções base do yt-dlp
            url: URL do vídeo
            use_tor: Se True, usa proxy Tor
        
        Returns:
            dict com 'success' (bool) e 'error' (str ou None)
        """
        # Usar o método to_ydl_opts da estratégia
        ydl_opts = strategy.to_ydl_opts(base_opts)
        
        # Adicionar proxy Tor se solicitado
        if use_tor:
            ydl_opts['proxy'] = TOR_PROXY_URL
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {'success': True, 'error': None, 'info': info}
                else:
                    return {'success': False, 'error': 'No info returned'}
        except Exception as e:
            error_msg = str(e)
            return {'success': False, 'error': error_msg}
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_android_client_with_tor(self, base_ydl_opts):
        """Testa estratégia android_client com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: android_client (priority 1) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'android_client')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ android_client com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
            print(f"   Duração: {result['info'].get('duration', 0)} segundos")
        else:
            print(f"❌ android_client com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_android_music_with_tor(self, base_ydl_opts):
        """Testa estratégia android_music com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: android_music (priority 2) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'android_music')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ android_music com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ android_music com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_ios_client_with_tor(self, base_ydl_opts):
        """Testa estratégia ios_client com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: ios_client (priority 3) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'ios_client')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ ios_client com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ ios_client com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_web_embed_with_tor(self, base_ydl_opts):
        """Testa estratégia web_embed com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: web_embed (priority 4) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'web_embed')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ web_embed com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ web_embed com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_tv_embedded_with_tor(self, base_ydl_opts):
        """Testa estratégia tv_embedded com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: tv_embedded (priority 5) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'tv_embedded')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ tv_embedded com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ tv_embedded com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_mweb_with_tor(self, base_ydl_opts):
        """Testa estratégia mweb com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: mweb (priority 6) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'mweb')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ mweb com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ mweb com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_default_with_tor(self, base_ydl_opts):
        """Testa estratégia default com Tor."""
        print("\n" + "="*80)
        print("TESTANDO: default (priority 7) com TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategy = next(s for s in manager.get_strategies() if s.name == 'default')
        
        result = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL)
        
        if result['success']:
            print(f"✅ default com Tor: SUCESSO")
            print(f"   Vídeo: {result['info'].get('title', 'N/A')}")
        else:
            print(f"❌ default com Tor: FALHOU")
            print(f"   Erro: {result['error'][:200]}")
        
        print("="*80)
        assert not result['error'] or result['success']
    
    @pytest.mark.integration
    @pytest.mark.requires_network
    def test_all_strategies_with_tor_summary(self, base_ydl_opts):
        """Testa todas as estratégias com Tor e gera relatório comparativo."""
        print("\n" + "="*80)
        print("TESTANDO TODAS AS ESTRATÉGIAS COM TOR")
        print("="*80)
        
        manager = DownloadStrategyManager(enable_multi_strategy=True)
        strategies = manager.get_strategies()
        
        results_with_tor = []
        results_without_tor = []
        
        for strategy in strategies:
            print(f"\n🧅 Testando {strategy.name} COM Tor...")
            result_tor = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL, use_tor=True)
            results_with_tor.append({
                'strategy': strategy.name,
                'priority': strategy.priority,
                'success': result_tor['success'],
                'error': result_tor['error']
            })
            
            print(f"🌐 Testando {strategy.name} SEM Tor...")
            result_no_tor = self.download_with_strategy(strategy, base_ydl_opts, TEST_VIDEO_URL, use_tor=False)
            results_without_tor.append({
                'strategy': strategy.name,
                'priority': strategy.priority,
                'success': result_no_tor['success'],
                'error': result_no_tor['error']
            })
        
        # Gerar resumo comparativo
        print("\n" + "="*80)
        print("RESUMO COMPARATIVO: TOR vs DIRETO")
        print("="*80)
        
        working_with_tor = [r for r in results_with_tor if r['success']]
        working_without_tor = [r for r in results_without_tor if r['success']]
        
        print(f"\n✅ Estratégias funcionando COM Tor: {len(working_with_tor)}/7")
        for r in working_with_tor:
            print(f"   - {r['strategy']} (priority {r['priority']})")
        
        print(f"\n✅ Estratégias funcionando SEM Tor: {len(working_without_tor)}/7")
        for r in working_without_tor:
            print(f"   - {r['strategy']} (priority {r['priority']})")
        
        # Estratégias que só funcionam com Tor
        only_tor = [r for r in results_with_tor 
                   if r['success'] and not any(x['strategy'] == r['strategy'] and x['success'] 
                                               for x in results_without_tor)]
        
        if only_tor:
            print(f"\n🎯 Estratégias que SÓ funcionam com Tor: {len(only_tor)}")
            for r in only_tor:
                print(f"   - {r['strategy']} (priority {r['priority']})")
        
        # Estratégias que pararam de funcionar com Tor
        broken_by_tor = [r for r in results_without_tor 
                        if r['success'] and not any(x['strategy'] == r['strategy'] and x['success'] 
                                                    for x in results_with_tor)]
        
        if broken_by_tor:
            print(f"\n⚠️ Estratégias que PARAM de funcionar com Tor: {len(broken_by_tor)}")
            for r in broken_by_tor:
                print(f"   - {r['strategy']} (priority {r['priority']})")
        
        # Recomendação
        print("\n" + "="*80)
        if len(working_with_tor) > len(working_without_tor):
            print("🎯 RECOMENDAÇÃO: Usar TOR")
            print(f"   Tor aumentou de {len(working_without_tor)} para {len(working_with_tor)} estratégias funcionando")
            best_strategy = working_with_tor[0]['strategy'] if working_with_tor else None
            if best_strategy:
                print(f"   Melhor estratégia: {best_strategy}")
        elif len(working_with_tor) < len(working_without_tor):
            print("🎯 RECOMENDAÇÃO: NÃO usar TOR")
            print(f"   Tor reduziu de {len(working_without_tor)} para {len(working_with_tor)} estratégias funcionando")
            best_strategy = working_without_tor[0]['strategy'] if working_without_tor else None
            if best_strategy:
                print(f"   Melhor estratégia: {best_strategy}")
        else:
            print("🎯 RECOMENDAÇÃO: Indiferente")
            print(f"   Mesma quantidade ({len(working_with_tor)}) funciona com ou sem Tor")
        
        print("="*80)
        
        # Salvar relatório
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_video': TEST_VIDEO_URL,
            'results_with_tor': results_with_tor,
            'results_without_tor': results_without_tor,
            'working_with_tor': len(working_with_tor),
            'working_without_tor': len(working_without_tor),
            'only_tor': [r['strategy'] for r in only_tor],
            'broken_by_tor': [r['strategy'] for r in broken_by_tor]
        }
        
        report_path = Path('test_strategies_tor_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Relatório JSON salvo em: {report_path}")
        
        # Gerar relatório de texto também
        txt_report_path = Path('test_strategies_tor_report.txt')
        with open(txt_report_path, 'w', encoding='utf-8') as f:
            f.write("RELATÓRIO DE TESTE: TOR vs DIRETO\n")
            f.write("="*80 + "\n\n")
            f.write(f"Vídeo testado: {TEST_VIDEO_URL}\n")
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"COM TOR: {len(working_with_tor)}/7 funcionando\n")
            for r in working_with_tor:
                f.write(f"  ✅ {r['strategy']} (priority {r['priority']})\n")
            
            f.write(f"\nSEM TOR: {len(working_without_tor)}/7 funcionando\n")
            for r in working_without_tor:
                f.write(f"  ✅ {r['strategy']} (priority {r['priority']})\n")
            
            if only_tor:
                f.write(f"\nSÓ COM TOR: {len(only_tor)}\n")
                for r in only_tor:
                    f.write(f"  🧅 {r['strategy']}\n")
            
            if broken_by_tor:
                f.write(f"\nQUEBRADAS COM TOR: {len(broken_by_tor)}\n")
                for r in broken_by_tor:
                    f.write(f"  ❌ {r['strategy']}\n")
        
        print(f"📄 Relatório TXT salvo em: {txt_report_path}")
        print("="*80)
