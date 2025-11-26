"""
F5-TTS Model Loader - Carregador Customizado para Modelo pt-BR
Sprint 3: Adaptação de Código

Responsável por carregar o modelo F5-TTS pt-BR com configurações customizadas
identificadas no Sprint 1.
"""

import torch
from pathlib import Path
from typing import Optional
from safetensors import safe_open

from f5_tts.model.cfm import CFM
from f5_tts.model.backbones.dit import DiT

from app.config import get_settings

# Carregar configurações globais
_settings = get_settings()


class F5TTSModelLoader:
    """
    Carregador customizado para o modelo F5-TTS pt-BR.
    
    Configurações identificadas no Sprint 1.2:
    - dim=1024, depth=22, heads=16, dim_head=64
    - ff_mult=2 (ao invés de 4 padrão)
    - mel_dim=100
    - text_num_embeds=2545 (vocabulário customizado)
    - text_dim=512 (ao invés de 100 padrão)
    - conv_layers=4 (4 blocos ConvNeXtV2)
    """
    
    # Configurações exatas do modelo pt-BR
    MODEL_CONFIG = {
        'dim': 1024,
        'depth': 22,
        'heads': 16,
        'dim_head': 64,
        'ff_mult': 2,              # CRITICAL: 2 ao invés de 4
        'mel_dim': 100,            # CRITICAL: 100 (input = mel*2 + text = 712)
        'text_num_embeds': 2545,   # CRITICAL: Vocabulário customizado
        'text_dim': 512,           # CRITICAL: 512 ao invés de 100
        'conv_layers': 4,          # CRITICAL: 4 blocos ConvNeXtV2
    }
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None
    ):
        """
        Inicializa o carregador.
        
        Args:
            model_path: Caminho para o checkpoint .safetensors
            device: Device para carregar o modelo ('cuda', 'cpu', ou None para auto)
        """
        self.model_path = Path(model_path or _settings['F5TTS_MODEL_PATH'])
        self.device = device or self._get_device()
        self.model = None
        
    def _get_device(self) -> str:
        """Determina o device automaticamente."""
        if torch.cuda.is_available():
            return 'cuda'
        return 'cpu'
    
    def load_model(self) -> CFM:
        """
        Carrega o modelo F5-TTS com as configurações pt-BR.
        
        Returns:
            Modelo CFM carregado e pronto para uso
            
        Raises:
            FileNotFoundError: Se o checkpoint não for encontrado
            RuntimeError: Se houver erro ao carregar os pesos
        """
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Checkpoint não encontrado: {self.model_path}\n"
                f"Certifique-se de que o modelo está em {self.model_path.parent}"
            )
        
        # Otimização: verificar se deve usar FP16
        use_fp16 = _settings['f5tts']['use_fp16'] and self.device == 'cuda'
        dtype = torch.float16 if use_fp16 else torch.float32
        
        print(f"📦 Instanciando DiT com configurações pt-BR...")
        print(f"   Device: {self.device}, Dtype: {dtype}")
        
        # 1. Instanciar backbone DiT com configurações customizadas
        dit = DiT(**self.MODEL_CONFIG)
        
        # 2. Wrappear com CFM
        print(f"📦 Criando modelo CFM...")
        model = CFM(transformer=dit)
        
        total_params = sum(p.numel() for p in model.parameters())
        print(f"   Parâmetros totais: {total_params:,}")
        
        # 3. Carregar checkpoint usando safetensors
        print(f"📂 Carregando checkpoint: {self.model_path.name}")
        
        # OTIMIZAÇÃO: Carregar diretamente no device de destino
        with safe_open(str(self.model_path), framework="pt", device=str(self.device)) as f:
            state_dict = {key: f.get_tensor(key) for key in f.keys()}
        
        print(f"   Tensors no checkpoint: {len(state_dict)}")
        
        # 4. Converter para FP16 se necessário
        if use_fp16:
            print(f"🔧 Convertendo para FP16...")
            state_dict = {k: v.half() if v.dtype == torch.float32 else v 
                         for k, v in state_dict.items()}
        
        # 5. Carregar pesos no modelo (modelo ainda está em CPU)
        print(f"⚙️  Carregando pesos...")
        result = model.load_state_dict(state_dict, strict=False)
        
        # Validar carregamento
        if len(result.missing_keys) > 0:
            print(f"   ⚠️  Missing keys: {len(result.missing_keys)}")
            print(f"      Primeiras: {result.missing_keys[:5]}")
        
        if len(result.unexpected_keys) > 0:
            print(f"   ⚠️  Unexpected keys: {len(result.unexpected_keys)}")
            print(f"      Primeiras: {result.unexpected_keys[:5]}")
        
        if len(result.missing_keys) == 0 and len(result.unexpected_keys) == 0:
            print(f"   ✅ Modelo carregado perfeitamente!")
        
        # 6. Mover para device (já carregado em GPU, mas precisa mover modelo base)
        print(f"🔧 Movendo modelo para {self.device}...")
        model = model.to(self.device)
        
        # 7. Configurar para inferência
        model.eval()
        
        # 8. Limpar cache se CUDA
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        
        print(f"✅ Modelo F5-TTS pt-BR pronto para uso!")
        print(f"   Device: {self.device}")
        print(f"   Dtype: {next(model.parameters()).dtype}")
        print(f"   Configurações: {self.MODEL_CONFIG}")
        
        self.model = model
        return model
    
    def get_model_info(self) -> dict:
        """
        Retorna informações sobre o modelo carregado.
        
        Returns:
            Dicionário com informações do modelo
        """
        if self.model is None:
            return {'status': 'not_loaded'}
        
        total_params = sum(p.numel() for p in self.model.parameters())
        
        return {
            'status': 'loaded',
            'model_path': str(self.model_path),
            'device': self.device,
            'total_parameters': total_params,
            'config': self.MODEL_CONFIG,
            'cuda_available': torch.cuda.is_available(),
            'gpu_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }


def load_f5tts_ptbr(
    model_path: Optional[str] = None,
    device: Optional[str] = None
) -> CFM:
    """
    Função auxiliar para carregar o modelo F5-TTS pt-BR.
    
    Args:
        model_path: Caminho para o checkpoint (opcional)
        device: Device para carregar ('cuda', 'cpu', ou None)
        
    Returns:
        Modelo CFM carregado
        
    Example:
        >>> model = load_f5tts_ptbr()
        >>> # Modelo pronto para inferência
    """
    loader = F5TTSModelLoader(model_path=model_path, device=device)
    return loader.load_model()
