"""
Feature Flags para controle de rollout gradual do sistema multi-engine.

Permite habilitar/desabilitar features específicas sem redeploy,
controlando o rollout de F5-TTS engine de forma segura.
"""

import os
from typing import Optional, Dict, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class RolloutPhase(Enum):
    """Fases do rollout gradual."""
    DISABLED = "disabled"  # Feature completamente desabilitada
    ALPHA = "alpha"  # 10% dos usuários
    BETA = "beta"  # 50% dos usuários
    GA = "ga"  # 100% (General Availability)


@dataclass
class FeatureFlag:
    """Definição de uma feature flag."""
    name: str
    enabled: bool
    phase: RolloutPhase
    description: str
    percentage: int = 0  # Porcentagem de usuários (0-100)
    whitelist: Set[str] = None  # IDs de usuários que sempre têm acesso
    blacklist: Set[str] = None  # IDs de usuários que nunca têm acesso
    
    def __post_init__(self):
        if self.whitelist is None:
            self.whitelist = set()
        if self.blacklist is None:
            self.blacklist = set()


class FeatureFlagManager:
    """
    Gerenciador de feature flags para rollout gradual.
    
    Exemplo de uso:
        manager = FeatureFlagManager()
        
        # Verificar se F5-TTS está habilitado para este usuário
        if manager.is_enabled('f5tts_engine', user_id='user_123'):
            engine = 'f5tts'
        else:
            engine = 'xtts'
    """
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self._load_flags_from_env()
        self._initialize_default_flags()
    
    def _load_flags_from_env(self):
        """Carrega configuração de feature flags de variáveis de ambiente."""
        # F5-TTS engine rollout
        f5tts_enabled = os.getenv('FEATURE_F5TTS_ENABLED', 'false').lower() == 'true'
        f5tts_phase = os.getenv('FEATURE_F5TTS_PHASE', 'disabled').lower()
        f5tts_percentage = int(os.getenv('FEATURE_F5TTS_PERCENTAGE', '0'))
        
        # Auto transcription (F5-TTS)
        auto_transcription_enabled = os.getenv('FEATURE_AUTO_TRANSCRIPTION_ENABLED', 'false').lower() == 'true'
        auto_transcription_phase = os.getenv('FEATURE_AUTO_TRANSCRIPTION_PHASE', 'disabled').lower()
        
        # Quality profiles
        quality_profiles_enabled = os.getenv('FEATURE_QUALITY_PROFILES_ENABLED', 'true').lower() == 'true'
        
        self._config_from_env = {
            'f5tts_engine': {
                'enabled': f5tts_enabled,
                'phase': f5tts_phase,
                'percentage': f5tts_percentage
            },
            'auto_transcription': {
                'enabled': auto_transcription_enabled,
                'phase': auto_transcription_phase
            },
            'quality_profiles': {
                'enabled': quality_profiles_enabled
            }
        }
    
    def _initialize_default_flags(self):
        """Inicializa feature flags padrão."""
        # F5-TTS Engine
        f5tts_config = self._config_from_env.get('f5tts_engine', {})
        self.flags['f5tts_engine'] = FeatureFlag(
            name='f5tts_engine',
            enabled=f5tts_config.get('enabled', False),
            phase=RolloutPhase(f5tts_config.get('phase', 'disabled')),
            description='F5-TTS engine (alternativa ao XTTS)',
            percentage=f5tts_config.get('percentage', 0)
        )
        
        # Auto-transcription (F5-TTS)
        auto_config = self._config_from_env.get('auto_transcription', {})
        self.flags['auto_transcription'] = FeatureFlag(
            name='auto_transcription',
            enabled=auto_config.get('enabled', False),
            phase=RolloutPhase(auto_config.get('phase', 'disabled')),
            description='Auto-transcrição de áudio de referência (Whisper)',
            percentage=0
        )
        
        # Quality Profiles
        quality_config = self._config_from_env.get('quality_profiles', {})
        self.flags['quality_profiles'] = FeatureFlag(
            name='quality_profiles',
            enabled=quality_config.get('enabled', True),
            phase=RolloutPhase.GA,
            description='Perfis de qualidade (fast/balanced/quality)',
            percentage=100
        )
    
    def is_enabled(self, feature_name: str, user_id: Optional[str] = None) -> bool:
        """
        Verifica se uma feature está habilitada para um usuário específico.
        
        Args:
            feature_name: Nome da feature flag
            user_id: ID do usuário (opcional)
        
        Returns:
            True se a feature está habilitada, False caso contrário
        """
        flag = self.flags.get(feature_name)
        if not flag:
            return False
        
        # Feature completamente desabilitada
        if not flag.enabled or flag.phase == RolloutPhase.DISABLED:
            return False
        
        # Verificar blacklist
        if user_id and user_id in flag.blacklist:
            return False
        
        # Verificar whitelist
        if user_id and user_id in flag.whitelist:
            return True
        
        # GA = habilitado para todos
        if flag.phase == RolloutPhase.GA:
            return True
        
        # Sem user_id, usar apenas enabled flag
        if not user_id:
            return flag.enabled
        
        # Rollout baseado em porcentagem (hash do user_id)
        # Isso garante que o mesmo usuário sempre terá o mesmo resultado
        user_hash = hash(user_id) % 100
        return user_hash < flag.percentage
    
    def get_flag(self, feature_name: str) -> Optional[FeatureFlag]:
        """Retorna a feature flag completa."""
        return self.flags.get(feature_name)
    
    def add_to_whitelist(self, feature_name: str, user_id: str):
        """Adiciona um usuário à whitelist de uma feature."""
        flag = self.flags.get(feature_name)
        if flag:
            flag.whitelist.add(user_id)
    
    def add_to_blacklist(self, feature_name: str, user_id: str):
        """Adiciona um usuário à blacklist de uma feature."""
        flag = self.flags.get(feature_name)
        if flag:
            flag.blacklist.add(user_id)
    
    def set_phase(self, feature_name: str, phase: RolloutPhase, percentage: int = 0):
        """
        Define a fase de rollout de uma feature.
        
        Args:
            feature_name: Nome da feature
            phase: Fase do rollout (DISABLED, ALPHA, BETA, GA)
            percentage: Porcentagem de usuários (para fases ALPHA/BETA)
        """
        flag = self.flags.get(feature_name)
        if flag:
            flag.phase = phase
            flag.percentage = percentage
            
            # Atualizar enabled baseado na fase
            flag.enabled = phase != RolloutPhase.DISABLED
    
    def get_all_flags(self) -> Dict[str, Dict]:
        """Retorna todas as feature flags em formato dict."""
        return {
            name: {
                'enabled': flag.enabled,
                'phase': flag.phase.value,
                'description': flag.description,
                'percentage': flag.percentage,
                'whitelist_count': len(flag.whitelist),
                'blacklist_count': len(flag.blacklist)
            }
            for name, flag in self.flags.items()
        }


# Singleton global
_feature_flag_manager = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Retorna o gerenciador global de feature flags (singleton)."""
    global _feature_flag_manager
    if _feature_flag_manager is None:
        _feature_flag_manager = FeatureFlagManager()
    return _feature_flag_manager


def is_feature_enabled(feature_name: str, user_id: Optional[str] = None) -> bool:
    """
    Helper function para verificar se uma feature está habilitada.
    
    Exemplo:
        if is_feature_enabled('f5tts_engine', user_id='user_123'):
            engine = 'f5tts'
    """
    manager = get_feature_flag_manager()
    return manager.is_enabled(feature_name, user_id)
