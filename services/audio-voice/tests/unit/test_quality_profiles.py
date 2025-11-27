"""
Testes unitários para sistema de perfis de qualidade
"""
import pytest
from app.models import QualityProfile, XTTSParameters


class TestQualityProfiles:
    """Testes para sistema de perfis de qualidade."""
    
    def test_quality_profile_enum(self):
        """Valida enum QualityProfile."""
        assert QualityProfile.BALANCED.value == "balanced"
        assert QualityProfile.EXPRESSIVE.value == "expressive"
        assert QualityProfile.STABLE.value == "stable"
    
    def test_xtts_parameters_balanced(self):
        """Valida parâmetros do perfil BALANCED."""
        params = XTTSParameters.from_profile(QualityProfile.BALANCED)
        
        assert params.temperature == 0.75
        assert params.repetition_penalty == 1.5
        assert params.top_p == 0.9
        assert params.top_k == 60
        assert params.length_penalty == 1.2
        assert params.speed == 1.0
        assert params.enable_text_splitting is False
    
    def test_xtts_parameters_expressive(self):
        """Valida parâmetros do perfil EXPRESSIVE."""
        params = XTTSParameters.from_profile(QualityProfile.EXPRESSIVE)
        
        assert params.temperature == 0.85
        assert params.repetition_penalty == 1.3
        assert params.top_p == 0.95
        assert params.top_k == 70
        assert params.length_penalty == 1.3
        assert params.speed == 0.98
        assert params.enable_text_splitting is False
    
    def test_xtts_parameters_stable(self):
        """Valida parâmetros do perfil STABLE."""
        params = XTTSParameters.from_profile(QualityProfile.STABLE)
        
        assert params.temperature == 0.70
        assert params.repetition_penalty == 1.7
        assert params.top_p == 0.85
        assert params.top_k == 55
        assert params.length_penalty == 1.1
        assert params.speed == 1.0
        assert params.enable_text_splitting is True
    
    def test_all_profiles_available(self):
        """Valida que todos os perfis têm parâmetros definidos."""
        for profile in QualityProfile:
            params = XTTSParameters.from_profile(profile)
            assert params is not None
            assert isinstance(params, XTTSParameters)
            
            # Valida ranges
            assert 0.0 <= params.temperature <= 1.0
            assert 1.0 <= params.repetition_penalty <= 5.0
            assert 0.0 <= params.top_p <= 1.0
            assert 1 <= params.top_k <= 100
            assert 0.5 <= params.speed <= 2.0
