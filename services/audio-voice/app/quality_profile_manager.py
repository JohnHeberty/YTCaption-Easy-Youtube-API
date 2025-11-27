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
        """Inicializa manager e carrega perfis padrão se necessário"""
        self._ensure_default_profiles()
    
    def _ensure_default_profiles(self):
        """Garante que perfis padrão existam no Redis"""
        try:
            # Verificar se já existem perfis
            xtts_profiles = self.list_profiles(TTSEngine.XTTS)
            f5tts_profiles = self.list_profiles(TTSEngine.F5TTS)
            
            # Criar perfis padrão XTTS se não existirem
            if not xtts_profiles:
                logger.info("Criando perfis padrão XTTS...")
                for profile in DEFAULT_XTTS_PROFILES.values():
                    self.create_profile(profile)
                logger.info(f"✅ {len(DEFAULT_XTTS_PROFILES)} perfis XTTS criados")
            
            # Criar perfis padrão F5-TTS se não existirem
            if not f5tts_profiles:
                logger.info("Criando perfis padrão F5-TTS...")
                for profile in DEFAULT_F5TTS_PROFILES.values():
                    self.create_profile(profile)
                logger.info(f"✅ {len(DEFAULT_F5TTS_PROFILES)} perfis F5-TTS criados")
                
        except Exception as e:
            logger.error(f"Erro ao criar perfis padrão: {e}")
    
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
        # Verificar se já existe
        existing = self.get_profile(profile.engine, profile.id)
        if existing:
            raise ValueError(f"Perfil {profile.id} já existe para engine {profile.engine}")
        
        # Atualizar timestamp
        profile.created_at = datetime.now()
        profile.updated_at = datetime.now()
        
        # Salvar no Redis
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
        profile_key = self._get_profile_key(engine, profile_id)
        profile_data = _redis_client.get(profile_key)
        
        if not profile_data:
            return None
        
        # Deserializar baseado no engine
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
        list_key = self._get_list_key(engine)
        profile_ids = _redis_client.smembers(list_key)
        
        if not profile_ids:
            return []
        
        profiles = []
        for profile_id in profile_ids:
            profile = self.get_profile(engine, profile_id)
            if profile:
                profiles.append(profile)
        
        # Ordenar: padrão primeiro, depois alfabético
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
        # Verificar se existe
        profile = self.get_profile(engine, profile_id)
        if not profile:
            return False
        
        # Não permitir deletar perfil padrão
        if profile.is_default:
            raise ValueError("Não é possível deletar perfil padrão")
        
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
        profiles = self.list_profiles(engine)
        for profile in profiles:
            if profile.is_default:
                return profile
        return None
    
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
        # Verificar se perfil existe
        new_default = self.get_profile(engine, profile_id)
        if not new_default:
            raise ValueError(f"Perfil {profile_id} não encontrado")
        
        # Remover flag is_default de todos os perfis
        profiles = self.list_profiles(engine)
        for profile in profiles:
            if profile.is_default and profile.id != profile_id:
                self.update_profile(engine, profile.id, {"is_default": False})
        
        # Definir novo padrão
        self.update_profile(engine, profile_id, {"is_default": True})
        
        logger.info(f"✅ Perfil padrão atualizado: {profile_id} ({engine})")
        return True


# Singleton global
quality_profile_manager = QualityProfileManager()
