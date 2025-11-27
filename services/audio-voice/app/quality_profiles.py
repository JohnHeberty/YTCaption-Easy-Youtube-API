"""
Quality Profiles System - Engine-Specific Audio Quality Presets
Perfis de qualidade separados por engine (XTTS e F5-TTS) com armazenamento Redis
"""
from enum import Enum
from typing import Optional, Dict, List, Any, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import json


class TTSEngine(str, Enum):
    """Engines TTS suportados"""
    XTTS = "xtts"
    F5TTS = "f5tts"


class BaseQualityProfile(BaseModel):
    """Base model para perfis de qualidade"""
    id: str = Field(..., description="ID único do perfil")
    name: str = Field(..., description="Nome do perfil")
    description: Optional[str] = Field(None, description="Descrição do perfil")
    engine: TTSEngine = Field(..., description="Engine TTS (xtts ou f5tts)")
    is_default: bool = Field(False, description="Se é perfil padrão do engine")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


class XTTSQualityProfile(BaseQualityProfile):
    """
    Perfil de qualidade específico para XTTS.
    
    Parâmetros otimizados para controlar:
    - Temperatura: Criatividade vs Estabilidade
    - Repetition Penalty: Evitar repetições
    - Top-P/Top-K: Amostragem probabilística
    - Length Penalty: Controle de duração
    - Speed: Velocidade da fala
    """
    engine: Literal[TTSEngine.XTTS] = Field(default=TTSEngine.XTTS)
    
    # === Parâmetros XTTS ===
    temperature: float = Field(
        default=0.75,
        ge=0.1,
        le=1.0,
        description="Temperatura (0.1-1.0): Maior = mais criativo, Menor = mais estável"
    )
    repetition_penalty: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Penalidade de repetição (1.0-3.0): Maior = menos repetições"
    )
    top_p: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Top-P nucleus sampling (0.5-1.0): Diversidade da amostragem"
    )
    top_k: int = Field(
        default=60,
        ge=10,
        le=100,
        description="Top-K sampling (10-100): Número de tokens candidatos"
    )
    length_penalty: float = Field(
        default=1.2,
        ge=0.5,
        le=2.0,
        description="Penalidade de comprimento (0.5-2.0): Controle de duração"
    )
    speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Velocidade da fala (0.5-2.0): Multiplier de velocidade"
    )
    enable_text_splitting: bool = Field(
        default=False,
        description="Dividir texto longo em sentenças (melhor para textos grandes)"
    )
    
    # === Metadados de qualidade ===
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Score de qualidade esperado (0-10)"
    )
    latency_ms: Optional[int] = Field(
        None,
        description="Latência esperada em ms"
    )
    stability_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Score de estabilidade (0-10)"
    )


class F5TTSQualityProfile(BaseQualityProfile):
    """
    Perfil de qualidade específico para F5-TTS.
    
    F5-TTS usa Flow Matching Diffusion e tem parâmetros diferentes do XTTS.
    Controla:
    - NFE Steps: Qualidade vs Velocidade (diffusion steps)
    - CFG Scale: Guidance para seguir referência
    - Speed: Velocidade da fala
    - Sway Sampling: Controle de variação
    - Edit Prompts: Modificadores de estilo
    """
    engine: Literal[TTSEngine.F5TTS] = Field(default=TTSEngine.F5TTS)
    
    # === Parâmetros F5-TTS ===
    nfe_step: int = Field(
        default=32,
        ge=8,
        le=64,
        description="Diffusion steps (8-64): Maior = melhor qualidade, mais lento. Recomendado: 32"
    )
    cfg_scale: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Classifier-free guidance (1.0-5.0): Controle da fidelidade à referência"
    )
    speed: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Velocidade da fala (0.5-2.0)"
    )
    sway_sampling_coef: float = Field(
        default=-1.0,
        ge=-1.0,
        le=1.0,
        description="Coeficiente de sway sampling (-1 a 1): Controle de variação. -1 = automático"
    )
    
    # === Controle de Qualidade de Áudio ===
    denoise_audio: bool = Field(
        default=True,
        description="Aplicar denoising no áudio de referência"
    )
    noise_reduction_strength: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Força da redução de ruído (0-1): Maior = mais agressivo"
    )
    
    # === Controle de Prosódia ===
    enhance_prosody: bool = Field(
        default=True,
        description="Melhorar prosódia (entonação, ritmo, ênfase)"
    )
    prosody_strength: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Força da melhoria de prosódia (0-1)"
    )
    
    # === Filtros de Pós-Processamento ===
    apply_normalization: bool = Field(
        default=True,
        description="Normalizar volume do áudio final"
    )
    target_loudness: float = Field(
        default=-20.0,
        ge=-30.0,
        le=-10.0,
        description="LUFS alvo para normalização (-30 a -10). Recomendado: -20"
    )
    apply_declipping: bool = Field(
        default=True,
        description="Remover clipping do áudio"
    )
    apply_deessing: bool = Field(
        default=True,
        description="Reduzir sibilância (sons 'S' e 'SH')"
    )
    deessing_frequency: int = Field(
        default=6000,
        ge=4000,
        le=10000,
        description="Frequência central para de-essing (Hz)"
    )
    
    # === Controle de Respiração e Pausas ===
    add_breathing: bool = Field(
        default=True,
        description="Adicionar sons de respiração naturais"
    )
    breathing_strength: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Intensidade da respiração (0-1)"
    )
    pause_optimization: bool = Field(
        default=True,
        description="Otimizar pausas entre frases"
    )
    
    # === Metadados de qualidade ===
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Score de qualidade esperado (0-10)"
    )
    latency_ms: Optional[int] = Field(
        None,
        description="Latência esperada em ms"
    )
    naturalness_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Score de naturalidade (0-10)"
    )


# Union type para ambos os perfis
QualityProfile = Union[XTTSQualityProfile, F5TTSQualityProfile]


class QualityProfileCreate(BaseModel):
    """Request para criar perfil de qualidade"""
    name: str = Field(..., description="Nome do perfil")
    description: Optional[str] = Field(None, description="Descrição")
    engine: TTSEngine = Field(..., description="Engine (xtts ou f5tts)")
    is_default: bool = Field(False, description="Definir como padrão")
    parameters: Dict[str, Any] = Field(..., description="Parâmetros específicos do engine")


class QualityProfileUpdate(BaseModel):
    """Request para atualizar perfil de qualidade"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None


class QualityProfileList(BaseModel):
    """Response com lista de perfis por engine"""
    xtts_profiles: List[XTTSQualityProfile] = Field(default_factory=list)
    f5tts_profiles: List[F5TTSQualityProfile] = Field(default_factory=list)
    total_count: int = 0


# === Perfis Padrão ===

DEFAULT_XTTS_PROFILES = {
    "balanced": XTTSQualityProfile(
        id="xtts_balanced",
        name="Balanced (Recomendado)",
        description="Equilíbrio entre qualidade e velocidade. Ideal para uso geral.",
        engine=TTSEngine.XTTS,
        is_default=True,
        temperature=0.75,
        repetition_penalty=1.5,
        top_p=0.9,
        top_k=60,
        length_penalty=1.2,
        speed=1.0,
        enable_text_splitting=False,
        quality_score=8.0,
        latency_ms=500,
        stability_score=9.0
    ),
    "expressive": XTTSQualityProfile(
        id="xtts_expressive",
        name="Expressive (Máxima Emoção)",
        description="Máxima expressividade e emoção. Pode ter pequenos artefatos.",
        engine=TTSEngine.XTTS,
        is_default=False,
        temperature=0.85,
        repetition_penalty=1.3,
        top_p=0.95,
        top_k=70,
        length_penalty=1.3,
        speed=0.98,
        enable_text_splitting=False,
        quality_score=7.5,
        latency_ms=550,
        stability_score=7.0
    ),
    "stable": XTTSQualityProfile(
        id="xtts_stable",
        name="Stable (Produção Segura)",
        description="Máxima estabilidade. Ideal para produção em larga escala.",
        engine=TTSEngine.XTTS,
        is_default=False,
        temperature=0.70,
        repetition_penalty=1.7,
        top_p=0.85,
        top_k=55,
        length_penalty=1.1,
        speed=1.0,
        enable_text_splitting=True,
        quality_score=8.5,
        latency_ms=450,
        stability_score=10.0
    )
}

DEFAULT_F5TTS_PROFILES = {
    "ultra_quality": F5TTSQualityProfile(
        id="f5tts_ultra_quality",
        name="Ultra Quality (Máxima Qualidade)",
        description="Qualidade máxima com todos os filtros. Melhor para audiolivros e conteúdo premium.",
        engine=TTSEngine.F5TTS,
        is_default=True,
        nfe_step=48,
        cfg_scale=2.5,
        speed=1.0,
        sway_sampling_coef=-1.0,
        denoise_audio=True,
        noise_reduction_strength=0.8,
        enhance_prosody=True,
        prosody_strength=0.9,
        apply_normalization=True,
        target_loudness=-20.0,
        apply_declipping=True,
        apply_deessing=True,
        deessing_frequency=6000,
        add_breathing=True,
        breathing_strength=0.4,
        pause_optimization=True,
        quality_score=9.5,
        latency_ms=2000,
        naturalness_score=9.8
    ),
    "balanced": F5TTSQualityProfile(
        id="f5tts_balanced",
        name="Balanced (Equilíbrio)",
        description="Equilíbrio entre qualidade e velocidade. Recomendado para uso geral.",
        engine=TTSEngine.F5TTS,
        is_default=False,
        nfe_step=32,
        cfg_scale=2.0,
        speed=1.0,
        sway_sampling_coef=-1.0,
        denoise_audio=True,
        noise_reduction_strength=0.7,
        enhance_prosody=True,
        prosody_strength=0.8,
        apply_normalization=True,
        target_loudness=-20.0,
        apply_declipping=True,
        apply_deessing=True,
        deessing_frequency=6000,
        add_breathing=True,
        breathing_strength=0.3,
        pause_optimization=True,
        quality_score=8.5,
        latency_ms=1500,
        naturalness_score=9.0
    ),
    "fast": F5TTSQualityProfile(
        id="f5tts_fast",
        name="Fast (Rápido)",
        description="Prioriza velocidade mantendo boa qualidade. Menos filtros de pós-processamento.",
        engine=TTSEngine.F5TTS,
        is_default=False,
        nfe_step=16,
        cfg_scale=1.5,
        speed=1.1,
        sway_sampling_coef=-1.0,
        denoise_audio=True,
        noise_reduction_strength=0.5,
        enhance_prosody=False,
        prosody_strength=0.5,
        apply_normalization=True,
        target_loudness=-20.0,
        apply_declipping=False,
        apply_deessing=False,
        deessing_frequency=6000,
        add_breathing=False,
        breathing_strength=0.2,
        pause_optimization=False,
        quality_score=7.5,
        latency_ms=800,
        naturalness_score=7.8
    )
}
