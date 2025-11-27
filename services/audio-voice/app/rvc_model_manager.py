"""
RVC Model Manager - Gerenciamento de modelos RVC
Sprint 6 - Green Phase (TDD)

Responsável por:
- Upload de modelos .pth e .index
- Listagem de modelos disponíveis
- Busca de modelo por ID
- Deleção de modelos
- Validação de arquivos de modelo
"""
import logging
import hashlib
import shutil
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
import torch

from .models import RvcModel
from .exceptions import RvcModelException, RvcModelNotFoundException

logger = logging.getLogger(__name__)


class RvcModelManager:
    """
    Gerencia modelos RVC (upload, listagem, deleção, validação)
    
    Storage:
        - Filesystem: arquivos .pth e .index
        - Metadata: JSON em disco (models_metadata.json)
    
    Thread-safety: Não implementado (single-process assumption)
    """
    
    def __init__(self, storage_dir: str = "/app/models/rvc"):
        """
        Inicializa RvcModelManager
        
        Args:
            storage_dir: Diretório para armazenar modelos
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata file
        self.metadata_file = self.storage_dir / "models_metadata.json"
        
        # In-memory cache de modelos
        self._models: Dict[str, RvcModel] = {}
        
        # Carrega modelos existentes
        self._load_metadata()
        
        logger.info(f"RvcModelManager initialized: {len(self._models)} models loaded")
    
    def _load_metadata(self):
        """Carrega metadata de modelos do disco"""
        if not self.metadata_file.exists():
            logger.info("No existing metadata file, starting fresh")
            return
        
        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
            
            for model_data in data.get('models', []):
                model = RvcModel(**model_data)
                self._models[model.id] = model
            
            logger.info(f"Loaded {len(self._models)} models from metadata")
        
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            # Inicia com cache vazio
            self._models = {}
    
    def _save_metadata(self):
        """Salva metadata de modelos no disco"""
        try:
            data = {
                'models': [model.dict() for model in self._models.values()],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug("Metadata saved successfully")
        
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            raise RvcModelException(f"Failed to save metadata: {e}")
    
    async def upload_model(
        self,
        name: str,
        pth_file: Path,
        index_file: Optional[Path] = None,
        description: Optional[str] = None,
        sample_rate: int = 40000,
        version: str = "v2"
    ) -> RvcModel:
        """
        Faz upload de modelo RVC
        
        Args:
            name: Nome do modelo
            pth_file: Path para arquivo .pth
            index_file: Path para arquivo .index (opcional)
            description: Descrição do modelo
            sample_rate: Sample rate do modelo (default 40kHz)
            version: Versão RVC (default v2)
        
        Returns:
            RvcModel: Modelo criado
        
        Raises:
            RvcModelException: Se upload falhar
        """
        logger.info(f"Uploading model: {name}")
        
        # Validações
        if not isinstance(pth_file, Path):
            pth_file = Path(pth_file)
        
        if not pth_file.exists():
            raise RvcModelException(f"Model file not found: {pth_file}")
        
        if not pth_file.suffix == '.pth':
            raise RvcModelException(f"Invalid file extension: {pth_file.suffix} (expected .pth)")
        
        # Valida arquivo .pth
        if not self.validate_model_file(pth_file):
            raise RvcModelException(f"Invalid model file: {pth_file}")
        
        # Gera ID único
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        hash_input = f"{name}_{timestamp}_{pth_file.stat().st_size}"
        model_id = f"rvc_{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"
        
        # Cria diretório do modelo
        model_dir = self.storage_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Copia arquivo .pth
        dest_pth = model_dir / f"{model_id}.pth"
        shutil.copy2(pth_file, dest_pth)
        logger.debug(f"Copied .pth to {dest_pth}")
        
        # Copia arquivo .index se fornecido
        dest_index = None
        if index_file is not None:
            if not isinstance(index_file, Path):
                index_file = Path(index_file)
            
            if not index_file.exists():
                logger.warning(f"Index file not found: {index_file}, skipping")
            else:
                dest_index = model_dir / f"{model_id}.index"
                shutil.copy2(index_file, dest_index)
                logger.debug(f"Copied .index to {dest_index}")
        
        # Cria RvcModel
        model = RvcModel.create_new(
            name=name,
            model_path=str(dest_pth),
            index_path=str(dest_index) if dest_index else None,
            description=description,
            sample_rate=sample_rate,
            version=version
        )
        
        # Sobrescreve ID gerado
        model.id = model_id
        
        # Adiciona ao cache
        self._models[model_id] = model
        
        # Salva metadata
        self._save_metadata()
        
        logger.info(f"Model uploaded successfully: {model_id}")
        
        return model
    
    def list_models(self, sort_by: str = "created_at") -> List[RvcModel]:
        """
        Lista todos modelos disponíveis
        
        Args:
            sort_by: Campo para ordenação (created_at, name)
        
        Returns:
            List[RvcModel]: Lista de modelos
        """
        models = list(self._models.values())
        
        # Ordenação
        if sort_by == "created_at":
            models.sort(key=lambda m: m.created_at, reverse=True)
        elif sort_by == "name":
            models.sort(key=lambda m: m.name.lower())
        
        return models
    
    def get_model(self, model_id: str) -> RvcModel:
        """
        Busca modelo por ID
        
        Args:
            model_id: ID do modelo
        
        Returns:
            RvcModel: Modelo encontrado
        
        Raises:
            ValueError: Se model_id for None
            RvcModelNotFoundException: Se modelo não existir
        """
        if model_id is None:
            raise ValueError("model_id cannot be None")
        
        if model_id not in self._models:
            raise RvcModelNotFoundException(f"Model not found: {model_id}")
        
        return self._models[model_id]
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Deleta modelo e seus arquivos
        
        Args:
            model_id: ID do modelo a deletar
        
        Returns:
            bool: True se deletado, False se não encontrado
        """
        if model_id not in self._models:
            logger.warning(f"Attempted to delete nonexistent model: {model_id}")
            return False
        
        model = self._models[model_id]
        
        logger.info(f"Deleting model: {model_id} ({model.name})")
        
        # Remove arquivos
        try:
            # Remove .pth
            pth_path = Path(model.pth_path)
            if pth_path.exists():
                pth_path.unlink()
                logger.debug(f"Removed {pth_path}")
            
            # Remove .index
            if model.index_path:
                index_path = Path(model.index_path)
                if index_path.exists():
                    index_path.unlink()
                    logger.debug(f"Removed {index_path}")
            
            # Remove diretório do modelo
            model_dir = pth_path.parent
            if model_dir.exists() and model_dir.is_dir():
                # Remove apenas se vazio ou contém apenas metadata
                try:
                    model_dir.rmdir()
                    logger.debug(f"Removed directory {model_dir}")
                except OSError:
                    # Diretório não vazio, deixa existir
                    logger.warning(f"Directory not empty, kept: {model_dir}")
        
        except Exception as e:
            logger.error(f"Error removing files for model {model_id}: {e}")
            # Continua mesmo com erro (remove do cache)
        
        # Remove do cache
        del self._models[model_id]
        
        # Salva metadata
        self._save_metadata()
        
        logger.info(f"Model deleted: {model_id}")
        
        return True
    
    def validate_model_file(self, pth_file: Path) -> bool:
        """
        Valida arquivo .pth de modelo RVC
        
        Args:
            pth_file: Path para arquivo .pth
        
        Returns:
            bool: True se válido, False caso contrário
        """
        if not isinstance(pth_file, Path):
            pth_file = Path(pth_file)
        
        if not pth_file.exists():
            logger.warning(f"Model file not found: {pth_file}")
            return False
        
        try:
            # Tenta carregar como PyTorch checkpoint
            checkpoint = torch.load(pth_file, map_location='cpu')
            
            # Validações básicas
            if not isinstance(checkpoint, dict):
                logger.warning(f"Invalid checkpoint format: not a dict")
                return False
            
            # RVC models geralmente têm key 'weight' ou 'model'
            # Validação flexível (aceita se é dict válido do PyTorch)
            
            logger.debug(f"Model file validated: {pth_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to validate model file: {e}")
            return False
    
    def get_model_stats(self) -> Dict:
        """
        Retorna estatísticas dos modelos
        
        Returns:
            Dict: Estatísticas (total, with_index, total_size)
        """
        total = len(self._models)
        with_index = sum(1 for m in self._models.values() if m.index_path)
        
        total_size = 0
        for model in self._models.values():
            try:
                pth_path = Path(model.pth_path)
                if pth_path.exists():
                    total_size += pth_path.stat().st_size
                
                if model.index_path:
                    index_path = Path(model.index_path)
                    if index_path.exists():
                        total_size += index_path.stat().st_size
            except Exception:
                pass
        
        return {
            'total_models': total,
            'models_with_index': with_index,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
    
    def clear_all_models(self):
        """
        DANGEROUS: Remove todos modelos
        
        Use apenas para testes ou reset completo
        """
        logger.warning("Clearing ALL models!")
        
        model_ids = list(self._models.keys())
        
        for model_id in model_ids:
            try:
                # Usa método assíncrono de forma síncrona (hack para simplificar)
                import asyncio
                asyncio.run(self.delete_model(model_id))
            except Exception as e:
                logger.error(f"Failed to delete model {model_id}: {e}")
        
        self._models.clear()
        self._save_metadata()
        
        logger.info("All models cleared")
