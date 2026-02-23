"""
Sistema inteligente de User-Agents com cache de erro e quarentena
"""
    
import os
import random
import logging
from typing import List, Set, Optional
from datetime import datetime, timedelta
from pathlib import Path
        
logger = logging.getLogger(__name__)
            
                
class UserAgentManager:
    """
    Gerenciador inteligente de User-Agents que:
    - Carrega User-Agents de arquivo
    - Mantém cache de User-Agents que deram erro
    - Aplica quarentena configurável para User-Agents problemáticos
    - Rotaciona User-Agents de forma inteligente
    """
    
    def __init__(
        self,
        user_agents_file: str = "user-agents.txt",
        quarantine_hours: int = 48,
        max_error_count: int = 3
    ):
        """
        Inicializa o gerenciador de User-Agents
        
        Args:
            user_agents_file: Caminho para arquivo com User-Agents
            quarantine_hours: Horas para quarentena de UAs problemáticos
            max_error_count: Máximo de erros antes de colocar em quarentena
        """
        self.user_agents_file = user_agents_file
        self.quarantine_hours = quarantine_hours
        self.max_error_count = max_error_count
        
        # Lista principal de User-Agents
        self.all_user_agents: List[str] = []
        
        # Cache de erros: {user_agent: {"count": int, "last_error": datetime}}
        self.error_cache: dict = {}
        
        # Set de User-Agents em quarentena temporária
        self.quarantined_uas: Set[str] = set()
        
        # Carrega User-Agents do arquivo
        self._load_user_agents()
        
        logger.info(f"UserAgentManager inicializado com {len(self.all_user_agents)} User-Agents")
        logger.info(f"Quarentena configurada para {quarantine_hours}h após {max_error_count} erros")
    
    def _load_user_agents(self) -> None:
        """Carrega User-Agents do arquivo com validação automática"""
        try:
            # Resolve caminho do arquivo
            if not os.path.isabs(self.user_agents_file):
                # Se não é caminho absoluto, procura relativo ao arquivo atual
                base_dir = Path(__file__).parent.parent
                user_agents_path = base_dir / self.user_agents_file
            else:
                user_agents_path = Path(self.user_agents_file)
            
            if not user_agents_path.exists():
                logger.warning(f"Arquivo {user_agents_path} não encontrado. Usando UAs padrão.")
                self._load_default_user_agents()
                return
            
            # Lê e processa arquivo com validação
            with open(user_agents_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Filtra e valida User-Agents
            user_agents = []
            invalid_count = 0
            
            for line_num, line in enumerate(lines, 1):
                ua = line.strip()
                
                # Ignora linhas vazias e comentários
                if not ua or ua.startswith('#'):
                    continue
                
                # Validação básica inline
                if self._is_valid_user_agent(ua):
                    user_agents.append(ua)
                else:
                    invalid_count += 1
                    if invalid_count <= 5:  # Log apenas os primeiros 5
                        logger.debug(f"UA inválido na linha {line_num}: {ua[:50]}...")
            
            if not user_agents:
                logger.warning("Nenhum User-Agent válido encontrado no arquivo.")
                self._load_default_user_agents()
                return
            
            self.all_user_agents = user_agents
            
            if invalid_count > 0:
                logger.warning(f"Filtrados {invalid_count} User-Agents inválidos")
            
            logger.info(f"Carregados {len(self.all_user_agents)} User-Agents válidos do arquivo")
            
        except Exception as e:
            logger.error(f"Erro ao carregar User-Agents: {e}")
            self._load_default_user_agents()
    
    def _is_valid_user_agent(self, ua: str) -> bool:
        """
        Validação rápida de User-Agent
        
        Args:
            ua: User-Agent string
            
        Returns:
            True se o UA é válido
        """
        # Verifica tamanho
        if len(ua) < 20 or len(ua) > 500:
            return False
        
        # Deve começar com Mozilla/
        if not ua.startswith('Mozilla/'):
            return False
        
        # Blacklist básica (bots, crawlers)
        blacklist_terms = [
            'bot', 'crawler', 'spider', 'scraper', 'fetcher',
            'slurp', 'archiver', 'wayback', 'curl/', 'wget/',
            'python-requests', 'libwww-perl', 'The given key was not present'
        ]
        
        ua_lower = ua.lower()
        for term in blacklist_terms:
            if term in ua_lower:
                return False
        
        # Deve conter pelo menos um browser legítimo
        browsers = ['chrome', 'firefox', 'safari', 'edge', 'opera', 'msie', 'trident']
        if not any(browser in ua_lower for browser in browsers):
            return False
        
        # Verifica caracteres válidos (ASCII printable)
        if not all(32 <= ord(c) <= 126 for c in ua):
            return False
        
        return True
    
    def _load_default_user_agents(self) -> None:
        """Carrega User-Agents padrão como fallback"""
        self.all_user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', # pylint: disable=line-too-long
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', # pylint: disable=line-too-long
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        logger.info(f"Usando {len(self.all_user_agents)} User-Agents padrão")
    
    def get_user_agent(self) -> str:
        """
        Retorna um User-Agent disponível (não em quarentena)
        
        Returns:
            User-Agent string válido
        """
        # Remove UAs expirados da quarentena
        self._cleanup_quarantine()
        
        # Filtra UAs disponíveis (não em quarentena)
        available_uas = [
            ua for ua in self.all_user_agents 
            if ua not in self.quarantined_uas
        ]
        
        # Se nenhum UA disponível, usar todos (emergência)
        if not available_uas:
            logger.warning("Todos os User-Agents estão em quarentena! Usando lista completa.")
            available_uas = self.all_user_agents
        
        # Retorna UA aleatório dos disponíveis
        selected_ua = random.choice(available_uas)
        
        logger.debug(f"User-Agent selecionado: {selected_ua[:50]}...")
        logger.debug(f"UAs disponíveis: {len(available_uas)}/{len(self.all_user_agents)}")
        
        return selected_ua
    
    def report_error(self, user_agent: str, error_details: Optional[str] = None) -> None:
        """
        Reporta erro para um User-Agent específico
        
        Args:
            user_agent: User-Agent que causou erro
            error_details: Detalhes opcionais do erro
        """
        now = datetime.now()
        
        # Inicializa ou atualiza cache de erro
        if user_agent not in self.error_cache:
            self.error_cache[user_agent] = {
                "count": 0,
                "first_error": now,
                "last_error": now,
                "details": []
            }
        
        # Incrementa contador
        self.error_cache[user_agent]["count"] += 1
        self.error_cache[user_agent]["last_error"] = now
        
        # Adiciona detalhes se fornecido
        if error_details:
            self.error_cache[user_agent]["details"].append({
                "timestamp": now,
                "error": error_details
            })
        
        error_count = self.error_cache[user_agent]["count"]
        
        logger.warning(f"Erro reportado para UA (erro #{error_count}): {user_agent[:50]}...")
        if error_details:
            logger.warning(f"Detalhes do erro: {error_details}")
        
        # Coloca em quarentena se atingiu limite
        if error_count >= self.max_error_count:
            self._quarantine_user_agent(user_agent)
    
    def _quarantine_user_agent(self, user_agent: str) -> None:
        """Coloca User-Agent em quarentena"""
        self.quarantined_uas.add(user_agent)
        quarantine_until = datetime.now() + timedelta(hours=self.quarantine_hours)
        
        # Armazena timestamp de quarentena
        if user_agent not in self.error_cache:
            self.error_cache[user_agent] = {}
        
        self.error_cache[user_agent]["quarantine_until"] = quarantine_until
        
        logger.warning(f"User-Agent colocado em quarentena até {quarantine_until}: {user_agent[:50]}...")
    
    def _cleanup_quarantine(self) -> None:
        """Remove User-Agents cuja quarentena expirou"""
        now = datetime.now()
        expired_uas = []
        
        for ua in list(self.quarantined_uas):
            if ua in self.error_cache and "quarantine_until" in self.error_cache[ua]:
                quarantine_until = self.error_cache[ua]["quarantine_until"]
                
                if now >= quarantine_until:
                    expired_uas.append(ua)
                    self.quarantined_uas.remove(ua)
                    
                    # Reset contador para dar nova chance
                    self.error_cache[ua]["count"] = 0
                    
                    logger.info(f"User-Agent liberado da quarentena: {ua[:50]}...")
        
        if expired_uas:
            logger.info(f"{len(expired_uas)} User-Agents liberados da quarentena")
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do gerenciador
        
        Returns:
            Dicionário com estatísticas
        """
        self._cleanup_quarantine()
        
        # Calcula qualidade média dos UAs
        sample_size = min(50, len(self.all_user_agents))
        if sample_size > 0:
            sample_uas = self.all_user_agents[:sample_size]
            quality_scores = [self._calculate_ua_quality(ua) for ua in sample_uas]
            avg_quality = sum(quality_scores) / len(quality_scores)
        else:
            avg_quality = 0.0
        
        return {
            "total_user_agents": len(self.all_user_agents),
            "quarantined_count": len(self.quarantined_uas),
            "available_count": len(self.all_user_agents) - len(self.quarantined_uas),
            "error_cache_size": len(self.error_cache),
            "quarantine_hours": self.quarantine_hours,
            "max_error_count": self.max_error_count,
            "average_quality": round(avg_quality, 2),
            "quarantined_uas": [ua[:60] + "..." if len(ua) > 60 else ua for ua in list(self.quarantined_uas)[:3]]
        }
    
    def _calculate_ua_quality(self, ua: str) -> float:
        """
        Calcula score de qualidade do UA (0.0 a 1.0)
        
        Args:
            ua: User-Agent string
            
        Returns:
            Score de qualidade
        """
        score = 0.0
        
        # Pontuações por critérios
        if ua.startswith('Mozilla/'):
            score += 0.25
        
        if 'AppleWebKit' in ua:
            score += 0.25
        
        if any(browser in ua for browser in ['Chrome', 'Firefox', 'Safari']):
            score += 0.25
        
        if 50 <= len(ua) <= 200:  # Tamanho ideal
            score += 0.25
        
        return min(score, 1.0)
    
    def reset_user_agent(self, user_agent: str) -> bool:
        """
        Remove User-Agent da quarentena e reseta cache de erro
        
        Args:
            user_agent: User-Agent para resetar
            
        Returns:
            True se foi resetado, False se não estava em cache
        """
        was_quarantined = user_agent in self.quarantined_uas
        
        # Remove da quarentena
        if user_agent in self.quarantined_uas:
            self.quarantined_uas.remove(user_agent)
        
        # Remove do cache de erro
        if user_agent in self.error_cache:
            del self.error_cache[user_agent]
            logger.info(f"Cache resetado para User-Agent: {user_agent[:50]}...")
            return True
        
        return was_quarantined