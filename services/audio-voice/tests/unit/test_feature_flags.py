"""
Testes para o sistema de feature flags.
"""

import pytest
from app.feature_flags import (
    FeatureFlagManager,
    FeatureFlag,
    RolloutPhase,
    is_feature_enabled,
    get_feature_flag_manager
)


class TestFeatureFlag:
    """Testes para a classe FeatureFlag."""
    
    def test_feature_flag_creation(self):
        """Testa criação básica de feature flag."""
        flag = FeatureFlag(
            name="test_feature",
            enabled=True,
            phase=RolloutPhase.ALPHA,
            description="Test feature",
            percentage=10
        )
        
        assert flag.name == "test_feature"
        assert flag.enabled is True
        assert flag.phase == RolloutPhase.ALPHA
        assert flag.percentage == 10
        assert len(flag.whitelist) == 0
        assert len(flag.blacklist) == 0
    
    def test_feature_flag_with_whitelist(self):
        """Testa feature flag com whitelist."""
        flag = FeatureFlag(
            name="test_feature",
            enabled=True,
            phase=RolloutPhase.ALPHA,
            description="Test",
            whitelist={"user_1", "user_2"}
        )
        
        assert "user_1" in flag.whitelist
        assert "user_2" in flag.whitelist
        assert "user_3" not in flag.whitelist


class TestFeatureFlagManager:
    """Testes para o gerenciador de feature flags."""
    
    def test_manager_initialization(self):
        """Testa inicialização do gerenciador."""
        manager = FeatureFlagManager()
        
        # Deve ter flags padrão
        assert 'f5tts_engine' in manager.flags
        assert 'auto_transcription' in manager.flags
        assert 'quality_profiles' in manager.flags
    
    def test_is_enabled_disabled_feature(self):
        """Testa feature completamente desabilitada."""
        manager = FeatureFlagManager()
        
        # Por padrão, F5-TTS está desabilitado
        assert manager.is_enabled('f5tts_engine') is False
        assert manager.is_enabled('f5tts_engine', user_id='user_123') is False
    
    def test_is_enabled_ga_feature(self):
        """Testa feature em GA (habilitada para todos)."""
        manager = FeatureFlagManager()
        
        # Quality profiles está em GA por padrão
        assert manager.is_enabled('quality_profiles') is True
        assert manager.is_enabled('quality_profiles', user_id='user_123') is True
        assert manager.is_enabled('quality_profiles', user_id='user_999') is True
    
    def test_is_enabled_with_whitelist(self):
        """Testa whitelist sobrescreve outras regras."""
        manager = FeatureFlagManager()
        
        # Habilitar feature mas em fase DISABLED
        flag = manager.flags['f5tts_engine']
        flag.enabled = False
        flag.phase = RolloutPhase.DISABLED
        
        # Adicionar usuário à whitelist
        manager.add_to_whitelist('f5tts_engine', 'vip_user')
        
        # Whitelist deve ter acesso mesmo com feature desabilitada
        assert manager.is_enabled('f5tts_engine', user_id='vip_user') is True
        assert manager.is_enabled('f5tts_engine', user_id='other_user') is False
    
    def test_is_enabled_with_blacklist(self):
        """Testa blacklist bloqueia acesso."""
        manager = FeatureFlagManager()
        
        # Habilitar feature em GA
        manager.set_phase('f5tts_engine', RolloutPhase.GA, percentage=100)
        
        # Adicionar usuário à blacklist
        manager.add_to_blacklist('f5tts_engine', 'blocked_user')
        
        # Blacklist deve bloquear mesmo em GA
        assert manager.is_enabled('f5tts_engine', user_id='blocked_user') is False
        assert manager.is_enabled('f5tts_engine', user_id='other_user') is True
    
    def test_percentage_rollout(self):
        """Testa rollout baseado em porcentagem."""
        manager = FeatureFlagManager()
        
        # Configurar ALPHA (10%)
        manager.set_phase('f5tts_engine', RolloutPhase.ALPHA, percentage=10)
        
        # Testar 100 usuários diferentes
        enabled_count = 0
        for i in range(100):
            user_id = f"user_{i}"
            if manager.is_enabled('f5tts_engine', user_id=user_id):
                enabled_count += 1
        
        # Deve estar próximo de 10% (com margem de erro)
        assert 5 <= enabled_count <= 15, f"Expected ~10%, got {enabled_count}%"
    
    def test_percentage_consistency(self):
        """Testa que mesmo usuário sempre tem mesmo resultado."""
        manager = FeatureFlagManager()
        manager.set_phase('f5tts_engine', RolloutPhase.ALPHA, percentage=50)
        
        user_id = "test_user"
        
        # Verificar 10 vezes
        results = [manager.is_enabled('f5tts_engine', user_id=user_id) for _ in range(10)]
        
        # Todos os resultados devem ser iguais (consistência)
        assert all(r == results[0] for r in results)
    
    def test_set_phase(self):
        """Testa mudança de fase."""
        manager = FeatureFlagManager()
        
        # Inicialmente desabilitado
        assert manager.flags['f5tts_engine'].phase == RolloutPhase.DISABLED
        
        # Mudar para ALPHA
        manager.set_phase('f5tts_engine', RolloutPhase.ALPHA, percentage=10)
        assert manager.flags['f5tts_engine'].phase == RolloutPhase.ALPHA
        assert manager.flags['f5tts_engine'].percentage == 10
        assert manager.flags['f5tts_engine'].enabled is True
        
        # Mudar para BETA
        manager.set_phase('f5tts_engine', RolloutPhase.BETA, percentage=50)
        assert manager.flags['f5tts_engine'].phase == RolloutPhase.BETA
        assert manager.flags['f5tts_engine'].percentage == 50
        
        # Mudar para GA
        manager.set_phase('f5tts_engine', RolloutPhase.GA, percentage=100)
        assert manager.flags['f5tts_engine'].phase == RolloutPhase.GA
        assert manager.is_enabled('f5tts_engine', user_id='any_user') is True
    
    def test_get_all_flags(self):
        """Testa obtenção de todas as flags."""
        manager = FeatureFlagManager()
        
        all_flags = manager.get_all_flags()
        
        assert 'f5tts_engine' in all_flags
        assert 'auto_transcription' in all_flags
        assert 'quality_profiles' in all_flags
        
        # Verificar estrutura
        f5tts = all_flags['f5tts_engine']
        assert 'enabled' in f5tts
        assert 'phase' in f5tts
        assert 'description' in f5tts
        assert 'percentage' in f5tts


class TestFeatureFlagHelpers:
    """Testes para funções helper."""
    
    def test_is_feature_enabled_helper(self):
        """Testa função helper is_feature_enabled."""
        # Deve usar singleton global
        result1 = is_feature_enabled('quality_profiles')
        result2 = is_feature_enabled('quality_profiles')
        
        assert result1 == result2  # Mesmo resultado (singleton)
        assert result1 is True  # Quality profiles está em GA
    
    def test_get_feature_flag_manager_singleton(self):
        """Testa que get_feature_flag_manager retorna singleton."""
        manager1 = get_feature_flag_manager()
        manager2 = get_feature_flag_manager()
        
        assert manager1 is manager2  # Mesmo objeto


class TestRolloutScenarios:
    """Testes de cenários reais de rollout."""
    
    def test_alpha_rollout_scenario(self):
        """Testa cenário de rollout ALPHA (10%)."""
        manager = FeatureFlagManager()
        
        # Fase ALPHA: 10% dos usuários
        manager.set_phase('f5tts_engine', RolloutPhase.ALPHA, percentage=10)
        
        # VIP users sempre têm acesso
        manager.add_to_whitelist('f5tts_engine', 'vip_user_1')
        manager.add_to_whitelist('f5tts_engine', 'vip_user_2')
        
        # VIP users devem ter acesso
        assert manager.is_enabled('f5tts_engine', user_id='vip_user_1') is True
        assert manager.is_enabled('f5tts_engine', user_id='vip_user_2') is True
        
        # ~10% dos usuários normais devem ter acesso
        normal_users_with_access = sum(
            1 for i in range(100)
            if manager.is_enabled('f5tts_engine', user_id=f'user_{i}')
        )
        assert 5 <= normal_users_with_access <= 15
    
    def test_beta_rollout_scenario(self):
        """Testa cenário de rollout BETA (50%)."""
        manager = FeatureFlagManager()
        
        # Fase BETA: 50% dos usuários
        manager.set_phase('f5tts_engine', RolloutPhase.BETA, percentage=50)
        
        # ~50% dos usuários devem ter acesso
        users_with_access = sum(
            1 for i in range(100)
            if manager.is_enabled('f5tts_engine', user_id=f'user_{i}')
        )
        assert 40 <= users_with_access <= 60
    
    def test_ga_rollout_scenario(self):
        """Testa cenário de rollout GA (100%)."""
        manager = FeatureFlagManager()
        
        # Fase GA: 100% dos usuários
        manager.set_phase('f5tts_engine', RolloutPhase.GA, percentage=100)
        
        # 100% dos usuários devem ter acesso
        users_with_access = sum(
            1 for i in range(100)
            if manager.is_enabled('f5tts_engine', user_id=f'user_{i}')
        )
        assert users_with_access == 100
        
        # Exceto blacklisted users
        manager.add_to_blacklist('f5tts_engine', 'blocked_user')
        assert manager.is_enabled('f5tts_engine', user_id='blocked_user') is False
    
    def test_rollback_scenario(self):
        """Testa cenário de rollback (voltar para DISABLED)."""
        manager = FeatureFlagManager()
        
        # Habilitar em GA
        manager.set_phase('f5tts_engine', RolloutPhase.GA, percentage=100)
        assert manager.is_enabled('f5tts_engine', user_id='user_1') is True
        
        # Rollback para DISABLED
        manager.set_phase('f5tts_engine', RolloutPhase.DISABLED, percentage=0)
        assert manager.is_enabled('f5tts_engine', user_id='user_1') is False
        
        # Mesmo VIP users não têm acesso após rollback
        manager.add_to_whitelist('f5tts_engine', 'vip_user')
        # Whitelist sobrescreve DISABLED
        assert manager.is_enabled('f5tts_engine', user_id='vip_user') is True
