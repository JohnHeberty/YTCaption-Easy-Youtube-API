"""
Quality Profiles Manager - Redis Storage
Gerenciador de perfis de qualidade com armazenamento Redis
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .quality_profiles import (
    TTSEngine,
    XTTSQualityProfile,
    F5TTSQualityProfile,
    QualityProfile,
    DEFAULT_XTTS_PROFILES,
    DEFAULT_F5TTS_PROFILES
)
from .config import get_settings
import redis

# Criar conexão Redis direta para quality profiles
settings = get_settings()
_redis_client = redis.Redis.from_url(settings['redis_url'], decode_responses=True)

logger = logging.getLogger(__name__)


class QualityProfileManager:
    """
    Gerenciador de perfis de qualidade com Redis.
    
    Armazena perfis separados por engine:
    - quality_profiles:xtts:{profile_id} -> XTTSQualityProfile
    - quality_profiles:f5tts:{profile_id} -> F5TTSQualityProfile
    - quality_profiles:xtts:list -> List[profile_ids]
    - quality_profiles:f5tts:list -> List[profile_ids]
    """
    
    REDIS_PREFIX_XTTS = "quality_profiles:xtts"
    REDIS_PREFIX_F5TTS = "quality_profiles:f5tts"
    REDIS_LIST_SUFFIX = "list"
    
    def __init__(self):
        """Inicializa manager sem persistir perfis padrão no Redis.

        - Perfis padrão ficam somente em código (imutáveis)
        - Apenas perfis customizados são salvos no Redis
        - Limpa do Redis quaisquer vestígios anteriores de perfis padrão
        """
        self._purge_default_profiles_from_redis()
    
    def _purge_default_profiles_from_redis(self):
        """Remove perfis padrão do Redis (não devem ser persistidos)."""
        try:
            default_xtts_ids = {p.id for p in DEFAULT_XTTS_PROFILES.values()}
            default_f5_ids = {p.id for p in DEFAULT_F5TTS_PROFILES.values()}

            # Deletar chaves individuais dos padrões
            for pid in default_xtts_ids:
                _redis_client.delete(f"{self.REDIS_PREFIX_XTTS}:{pid}")
            for pid in default_f5_ids:
                _redis_client.delete(f"{self.REDIS_PREFIX_F5TTS}:{pid}")

            # Remover IDs padrão das listas
            xtts_list_key = self._get_list_key(TTSEngine.XTTS)
            f5_list_key = self._get_list_key(TTSEngine.F5TTS)
            if _redis_client.exists(xtts_list_key):
                for pid in default_xtts_ids:
                    _redis_client.srem(xtts_list_key, pid)
            if _redis_client.exists(f5_list_key):
                for pid in default_f5_ids:
                    _redis_client.srem(f5_list_key, pid)
        except Exception as e:
            logger.warning(f"Falha ao limpar perfis padrão do Redis: {e}")

    def _is_default_profile_id(self, engine: TTSEngine, profile_id: str) -> bool:
        """Verifica se o ID pertence ao conjunto embutido de perfis padrão."""
        if engine == TTSEngine.XTTS:
            return profile_id in {p.id for p in DEFAULT_XTTS_PROFILES.values()}
        return profile_id in {p.id for p in DEFAULT_F5TTS_PROFILES.values()}
    
    def _get_prefix(self, engine: TTSEngine) -> str:
        """Retorna prefixo Redis para engine"""
        return self.REDIS_PREFIX_XTTS if engine == TTSEngine.XTTS else self.REDIS_PREFIX_F5TTS
    
    def _get_list_key(self, engine: TTSEngine) -> str:
        """Retorna chave da lista de perfis"""
        prefix = self._get_prefix(engine)
        return f"{prefix}:{self.REDIS_LIST_SUFFIX}"
    
    def _get_profile_key(self, engine: TTSEngine, profile_id: str) -> str:
        """Retorna chave do perfil"""
        prefix = self._get_prefix(engine)
        return f"{prefix}:{profile_id}"
    
    def create_profile(
        self,
        profile: QualityProfile
    ) -> QualityProfile:
        """
        Cria novo perfil de qualidade.
        
        Args:
            profile: Perfil (XTTSQualityProfile ou F5TTSQualityProfile)
        
        Returns:
            Perfil criado
        
        Raises:
            ValueError: Se perfil com mesmo ID já existe
        """
        # Bloquear IDs reservados de perfis padrão
        if self._is_default_profile_id(profile.engine, profile.id):
            raise ValueError("IDs de perfis padrão são reservados e não podem ser criados")

        # Verificar se já existe
        existing = self.get_profile(profile.engine, profile.id)
        if existing:
            raise ValueError(f"Perfil {profile.id} já existe para engine {profile.engine}")
        
        # Atualizar timestamp
        profile.created_at = datetime.now()
        profile.updated_at = datetime.now()
        
        # Salvar no Redis (somente custom)
        profile_key = self._get_profile_key(profile.engine, profile.id)
        profile_data = profile.json()
        _redis_client.set(profile_key, profile_data)
        
        # Adicionar à lista
        list_key = self._get_list_key(profile.engine)
        _redis_client.sadd(list_key, profile.id)
        
        logger.info(f"✅ Perfil criado: {profile.id} ({profile.engine})")
        return profile
    
    def get_profile(
        self,
        engine: TTSEngine,
        profile_id: str
    ) -> Optional[QualityProfile]:
        """
        Busca perfil por ID.
        
        Args:
            engine: Engine (xtts ou f5tts)
            profile_id: ID do perfil
        
        Returns:
            Perfil ou None se não encontrado
        """
        # Primeiro: perfis padrão (embutidos)
        if self._is_default_profile_id(engine, profile_id):
            if engine == TTSEngine.XTTS:
                for p in DEFAULT_XTTS_PROFILES.values():
                    if p.id == profile_id:
                        return p
            else:
                for p in DEFAULT_F5TTS_PROFILES.values():
                    if p.id == profile_id:
                        return p

        # Buscar apenas no Redis (custom)
        profile_key = self._get_profile_key(engine, profile_id)
        profile_data = _redis_client.get(profile_key)
        if not profile_data:
            return None
        if engine == TTSEngine.XTTS:
            return XTTSQualityProfile.parse_raw(profile_data)
        else:
            return F5TTSQualityProfile.parse_raw(profile_data)
    
    def list_profiles(
        self,
        engine: TTSEngine
    ) -> List[QualityProfile]:
        """
        Lista todos os perfis de um engine.
        
        Args:
            engine: Engine (xtts ou f5tts)
        
        Returns:
            Lista de perfis
        """
        profiles: List[QualityProfile] = []

        # Adicionar perfis padrão embutidos
        if engine == TTSEngine.XTTS:
            profiles.extend(DEFAULT_XTTS_PROFILES.values())
        else:
            profiles.extend(DEFAULT_F5TTS_PROFILES.values())

        # Adicionar customizados do Redis
        list_key = self._get_list_key(engine)
        if _redis_client.exists(list_key):
            profile_ids = _redis_client.smembers(list_key)
            for profile_id in profile_ids:
                if self._is_default_profile_id(engine, profile_id):
                    # Não incluir padrões do Redis
                    continue
                profile = self.get_profile(engine, profile_id)
                if profile:
                    profiles.append(profile)

        profiles.sort(key=lambda p: (not p.is_default, p.name))
        return profiles
    
    def list_all_profiles(self) -> Dict[str, List[QualityProfile]]:
        """
        Lista todos os perfis de todos os engines.
        
        Returns:
            Dict com chaves 'xtts' e 'f5tts'
        """
        return {
            "xtts": self.list_profiles(TTSEngine.XTTS),
            "f5tts": self.list_profiles(TTSEngine.F5TTS)
        }
    
    def update_profile(
        self,
        engine: TTSEngine,
        profile_id: str,
        updates: Dict[str, Any]
    ) -> Optional[QualityProfile]:
        """
        Atualiza perfil existente.
        
        Args:
            engine: Engine
            profile_id: ID do perfil
            updates: Dict com campos a atualizar
        
        Returns:
            Perfil atualizado ou None se não encontrado
        """
        # Bloquear alterações em perfis padrão
        if self._is_default_profile_id(engine, profile_id):
            raise ValueError("Perfis padrão são imutáveis e não podem ser atualizados")

        # Buscar perfil existente
        profile = self.get_profile(engine, profile_id)
        if not profile:
            return None
        
        # Atualizar campos
        profile_dict = profile.dict()
        profile_dict.update(updates)
        profile_dict['updated_at'] = datetime.now()
        
        # Recriar objeto
        if engine == TTSEngine.XTTS:
            updated_profile = XTTSQualityProfile(**profile_dict)
        else:
            updated_profile = F5TTSQualityProfile(**profile_dict)
        
        # Salvar
        profile_key = self._get_profile_key(engine, profile_id)
        _redis_client.set(profile_key, updated_profile.json())
        
        logger.info(f"✅ Perfil atualizado: {profile_id} ({engine})")
        return updated_profile
    
    def delete_profile(
        self,
        engine: TTSEngine,
        profile_id: str
    ) -> bool:
        """
        Deleta perfil.
        
        Args:
            engine: Engine
            profile_id: ID do perfil
        
        Returns:
            True se deletado, False se não encontrado
        """
        # Bloquear remoção de perfis padrão (embutidos)
        if self._is_default_profile_id(engine, profile_id):
            raise ValueError("Perfis padrão não podem ser deletados")

        # Verificar se existe (custom)
        profile = self.get_profile(engine, profile_id)
        if not profile:
            return False
        
        # Deletar do Redis
        profile_key = self._get_profile_key(engine, profile_id)
        _redis_client.delete(profile_key)
        
        # Remover da lista
        list_key = self._get_list_key(engine)
        _redis_client.srem(list_key, profile_id)
        
        logger.info(f"✅ Perfil deletado: {profile_id} ({engine})")
        return True
    
    def get_default_profile(
        self,
        engine: TTSEngine
    ) -> Optional[QualityProfile]:
        """
        Busca perfil padrão do engine.
        
        Args:
            engine: Engine
        
        Returns:
            Perfil padrão ou None
        """
        # Tentar usar um padrão atual configurado
        key = f"{self._get_prefix(engine)}:current_default"
        try:
            current_id = _redis_client.get(key)
            if current_id:
                prof = self.get_profile(engine, current_id)
                if prof:
                    return prof
        except Exception:
            pass

        # Caso contrário, retornar padrão embutido marcado como is_default
        defaults = DEFAULT_XTTS_PROFILES if engine == TTSEngine.XTTS else DEFAULT_F5TTS_PROFILES
        for p in defaults.values():
            if p.is_default:
                return p
        return list(defaults.values())[0] if defaults else None
    
    def set_default_profile(
        self,
        engine: TTSEngine,
        profile_id: str
    ) -> bool:
        """
        Define perfil como padrão (remove padrão de outros).
        
        Args:
            engine: Engine
            profile_id: ID do novo perfil padrão
        
        Returns:
            True se sucesso
        """
        # Definir perfil padrão atual via chave dedicada (não altera embutidos)
        new_default = self.get_profile(engine, profile_id)
        if not new_default:
            raise ValueError(f"Perfil {profile_id} não encontrado")
        key = f"{self._get_prefix(engine)}:current_default"
        _redis_client.set(key, profile_id)
        logger.info(f"✅ Padrão atual definido: {profile_id} ({engine})")
        return True


# Singleton global
quality_profile_manager = QualityProfileManager()
