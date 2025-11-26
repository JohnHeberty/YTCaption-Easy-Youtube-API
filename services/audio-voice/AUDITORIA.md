# AUDITORIA - Migração F5-TTS → XTTS

**Data:** 2025-01-26  
**Contexto:** Migração completa da arquitetura de TTS de F5-TTS (bugado) para XTTS (estável, production-proven)

## 📋 Resumo Executivo

### Motivação da Migração
- **F5-TTS:** Instável, bugs internos não-resolvíveis (`TypeError: encoding without a string argument`)
- **XTTS:** Comprovado em produção, 16 idiomas incluindo português, API simples e documentada
- **Resultado dos testes:** Clonagem funciona ✅ mas dubbing falha ❌ com F5-TTS

### Escopo da Auditoria
1. **Identificar** todas as dependências F5-TTS no projeto
2. **Classificar** cada item em: DELETE, MODIFY ou UPDATE
3. **Mapear** pontos de integração e acoplamento
4. **Estimar** impacto e riscos da migração

---

## 1. ARQUIVOS A DELETAR (F5-TTS Específicos)

### 1.1. Cliente F5-TTS (DELETAR COMPLETAMENTE)
**Arquivo:** `app/openvoice_client.py` (linhas 1-600+)

**Motivo:** Este arquivo é 100% acoplado ao F5-TTS:
- Importa `from f5_tts.api import F5TTS` (linha 95)
- Classe `F5TTSClient` com lógica específica F5-TTS
- Monkey patches para bugs do F5-TTS (linhas 33-70)
- Validações customizadas para workarounds F5-TTS

**Conteúdo a deletar:**
- Importações F5-TTS: `from f5_tts.api import F5TTS`
- Classe `F5TTSClient` inteira (300+ linhas)
- Métodos `_apply_chunk_text_patch()` (monkey patch)
- Métodos `_load_f5tts_model()`, `_validate_audio_for_cloning_f5()`
- Configurações F5-TTS específicas (model_dir, hf_cache_dir, nfe_step)

**Impacto:** ALTO - Arquivo central do serviço, requer substituição completa

---

### 1.2. Testes F5-TTS (DELETAR)
**Arquivos a deletar:**
- `tests/test_f5tts_import.py` (se existir)
- `tests/test_f5tts_basic.py` (se existir)
- `tests/integration/test_f5tts_integration.py` (se existir)

**Motivo:** Testes específicos para F5-TTS não servem para XTTS

**Impacto:** BAIXO - Testes serão recriados para XTTS

---

### 1.3. Documentação Obsoleta (DELETAR)
**Arquivos a deletar:**
- `CONVERTER.md` - Documentação da conversão OpenVoice→F5-TTS (obsoleto)
- `SPRINT.md` - Plano de sprints para F5-TTS (obsoleto)
- `VIDEO-SUPPORT.md` - Suporte a vídeo com F5-TTS (obsoleto)
- `EXAMPLES.md` - Exemplos de uso F5-TTS (obsoleto)
- `MODEL-MANAGEMENT.md` - Gestão de modelos F5-TTS (obsoleto)

**Motivo:** Documentação desatualizada, será substituída por docs XTTS

**Impacto:** BAIXO - Documentação será recriada

---

### 1.4. Scripts de Monitoramento F5-TTS (DELETAR)
**Arquivos a deletar:**
- `monitor_build_sprint2.sh` (se relacionado a F5-TTS)
- `monitor_build.sh` (se relacionado a F5-TTS)
- `run_clone_test.sh` (teste específico F5-TTS)

**Motivo:** Scripts de build/teste específicos do F5-TTS

**Impacto:** BAIXO - Scripts serão recriados para XTTS

---

### 1.5. Testes de Compatibilidade F5-TTS (DELETAR)
**Arquivos a deletar:**
- `test_f5tts_load.py`
- `test_f5tts_loader.py`
- `test_model_compatibility.py`
- `test_final_compatibility.py`

**Motivo:** Testes de carga/compatibilidade específicos F5-TTS

**Impacto:** BAIXO - Serão recriados para XTTS

---

## 2. ARQUIVOS A MODIFICAR (Interfaces Genéricas)

### 2.1. Processor Principal (MODIFICAR)
**Arquivo:** `app/processor.py`

**Linhas afetadas:**
- Linha 14: Import do cliente TTS
  ```python
  # ANTES
  from .openvoice_client import OpenVoiceClient
  
  # DEPOIS
  from .xtts_client import XTTSClient
  ```

- Linha 18-40: Factory Pattern para escolha de engine
  ```python
  # MODIFICAR
  def __init__(self):
      # Factory: escolhe motor por env var
      engine = os.getenv('TTS_ENGINE', 'xtts')  # CHANGE: default='xtts'
      
      if engine == 'xtts':
          self.tts_engine = XTTSClient(device=self.device)
      else:
          raise ValueError(f"Unsupported TTS engine: {engine}")
  ```

- Métodos afetados:
  - `process_dubbing_job()` - Chamadas ao cliente TTS
  - `process_voice_cloning_job()` - Chamadas ao cliente TTS
  - `_validate_audio()` - Validações específicas

**Impacto:** ALTO - Arquivo central do processamento

---

### 2.2. Configurações (MODIFICAR)
**Arquivo:** `app/config.py`

**Seção a REMOVER (linhas 72-102):**
```python
# DELETE ENTIRE SECTION
'f5tts': {
    'model': os.getenv('F5TTS_MODEL', 'F5-TTS'),
    'device': os.getenv('F5TTS_DEVICE', 'cuda'),
    'hf_cache_dir': os.getenv('F5TTS_CACHE', '/app/models/f5tts'),
    # ... (30 linhas de config F5-TTS)
},
'F5TTS_MODEL_PATH': ...
```

**Seção a ADICIONAR:**
```python
# ADD NEW SECTION
'xtts': {
    'model': os.getenv('XTTS_MODEL', 'tts_models/multilingual/multi-dataset/xtts_v2'),
    'device': os.getenv('XTTS_DEVICE', 'cuda'),
    'cache_dir': os.getenv('XTTS_CACHE', '/app/models/xtts'),
    'temperature': float(os.getenv('XTTS_TEMPERATURE', '0.7')),
    'repetition_penalty': float(os.getenv('XTTS_REPETITION_PENALTY', '2.0')),
    'length_penalty': float(os.getenv('XTTS_LENGTH_PENALTY', '1.0')),
    'top_k': int(os.getenv('XTTS_TOP_K', '50')),
    'top_p': float(os.getenv('XTTS_TOP_P', '0.85')),
    'speed': float(os.getenv('XTTS_SPEED', '1.0')),
    'enable_text_splitting': os.getenv('XTTS_ENABLE_TEXT_SPLITTING', 'true').lower() == 'true',
    'gpt_cond_len': int(os.getenv('XTTS_GPT_COND_LEN', '30')),  # segundos
    'max_ref_length': int(os.getenv('XTTS_MAX_REF_LENGTH', '30')),  # segundos
},
```

**Impacto:** MÉDIO - Configurações centralizadas

---

### 2.3. Modelos de Dados (MODIFICAR PARCIALMENTE)
**Arquivo:** `app/models.py`

**Classe `VoiceProfile`:**
- Campo `reference_text` - MANTER (usado por XTTS para conditioning)
- Campo `reference_audio_path` - MANTER (usado por XTTS)
- Métodos de validação - REVISAR (adaptar para requisitos XTTS)

**Classe `Job`:**
- Enum `JobStatus` - MANTER
- Campo `voice_id` - MANTER
- Métodos de progresso - MANTER

**Impacto:** BAIXO - Modelos são genéricos

---

### 2.4. Interface TTS (MODIFICAR)
**Arquivo:** `app/tts_interface.py` (se existir)

**Classe `TTSEngine` (Abstract Base Class):**
- Métodos abstratos:
  - `generate_dubbing()` - MANTER assinatura
  - `clone_voice()` - MANTER assinatura
  - `unload_models()` - MANTER assinatura

**Impacto:** BAIXO - Interface permanece a mesma

---

### 2.5. API Endpoints (MODIFICAR LEVEMENTE)
**Arquivo:** `app/main.py`

**Endpoints afetados:**
- `POST /voices/clone` - MANTER (apenas troca cliente interno)
- `POST /jobs` - MANTER (apenas troca cliente interno)
- `GET /jobs/{job_id}` - MANTER (sem mudanças)

**Mudanças:**
- Mensagens de log: "F5-TTS" → "XTTS"
- Health check: Verificar XTTS ao invés de F5-TTS

**Impacto:** BAIXO - API externa permanece compatível

---

### 2.6. Worker Celery (MODIFICAR LEVEMENTE)
**Arquivo:** `run_celery.py`

**Mudanças:**
- Import do processor (já usa abstração)
- Logs: "F5-TTS" → "XTTS"

**Impacto:** BAIXO - Worker usa processor abstrato

---

### 2.7. Validadores (MODIFICAR)
**Arquivo:** `app/validators.py` (se existir)

**Funções afetadas:**
- `validate_audio_for_cloning()` - ADAPTAR para requisitos XTTS
  - XTTS: Mínimo 3 segundos (F5-TTS tinha requisitos diferentes)
  - XTTS: Taxa de amostragem flexível (resample automático)

**Impacto:** MÉDIO - Validações críticas para qualidade

---

## 3. ARQUIVOS A ATUALIZAR (Dependências)

### 3.1. Dependências Python (ATUALIZAR)
**Arquivo:** `requirements.txt`

**REMOVER (dependências F5-TTS):**
```txt
f5-tts>=0.0.1
omegaconf>=2.3.0
hydra-core>=1.3.2
vocos>=0.1.0
cached-path>=1.5.2
```

**ADICIONAR (dependências XTTS):**
```txt
TTS>=0.22.0  # Coqui TTS com XTTS v2
# Dependências já incluídas no TTS:
#   - transformers
#   - torch
#   - torchaudio
#   - numpy
#   - scipy
```

**MANTER:**
```txt
torch==2.1.2
torchaudio==2.1.2
soundfile==0.12.1
librosa>=0.10.0
numpy>=1.24.0
scipy>=1.10.0
transformers>=4.35.0  # Whisper (usado por XTTS também)
```

**Impacto:** MÉDIO - Redução de dependências (TTS é all-in-one)

---

### 3.2. Constraints (ATUALIZAR)
**Arquivo:** `constraints.txt`

**VERIFICAR compatibilidade:**
- `numpy==1.26.4` - XTTS requer numpy>=1.23
- `torch==2.1.2` - XTTS suporta torch 2.x
- `scipy<1.13` - XTTS requer scipy>=1.10

**Impacto:** BAIXO - Constraints compatíveis

---

### 3.3. Docker (ATUALIZAR)
**Arquivo:** `Dockerfile`

**Seção de instalação Python:**
```dockerfile
# ANTES (F5-TTS build)
RUN pip install f5-tts vocos omegaconf hydra-core

# DEPOIS (XTTS via TTS package)
RUN pip install TTS>=0.22.0
```

**Volumes a ajustar:**
```dockerfile
# ANTES
VOLUME /app/models/f5tts

# DEPOIS
VOLUME /app/models/xtts
```

**Variáveis de ambiente:**
```dockerfile
# ADICIONAR
ENV XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
ENV XTTS_CACHE=/app/models/xtts
ENV XTTS_DEVICE=cuda
```

**Impacto:** MÉDIO - Rebuild de imagem Docker

---

### 3.4. Docker Compose (ATUALIZAR)
**Arquivo:** `docker-compose.yml`

**Variáveis de ambiente:**
```yaml
# REMOVER
F5TTS_MODEL: "F5-TTS"
F5TTS_CACHE: "/app/models/f5tts"
F5TTS_NFE_STEP: "16"

# ADICIONAR
XTTS_MODEL: "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_CACHE: "/app/models/xtts"
XTTS_TEMPERATURE: "0.7"
XTTS_REPETITION_PENALTY: "2.0"
```

**Volumes:**
```yaml
# ADICIONAR
- ./models/xtts:/app/models/xtts
```

**Impacto:** BAIXO - Apenas configurações

---

### 3.5. README (ATUALIZAR)
**Arquivo:** `README.md`

**Seções a atualizar:**
- "Features" - Substituir "F5-TTS" por "XTTS v2"
- "Dependencies" - Listar dependências XTTS
- "Configuration" - Documentar variáveis XTTS
- "Usage Examples" - Atualizar exemplos de API

**Impacto:** BAIXO - Documentação de uso

---

### 3.6. Arquivo de Teste (ATUALIZAR)
**Arquivo:** `test_voice_clone.py`

**Manter funcionalidade:**
- Teste de clonagem: MANTER (API não muda)
- Teste de dubbing: MANTER (API não muda)
- Logs: "F5-TTS" → "XTTS"

**Impacto:** BAIXO - Testes end-to-end continuam válidos

---

## 4. NOVOS ARQUIVOS A CRIAR

### 4.1. Cliente XTTS (CRIAR)
**Arquivo:** `app/xtts_client.py` (novo)

**Conteúdo:**
```python
"""
Cliente XTTS - Adapter para dublagem e clonagem de voz
Substituição completa do F5-TTS
"""
import logging
import torch
import torchaudio
from pathlib import Path
from typing import Optional, Tuple
from TTS.api import TTS
from TTS.tts.models.xtts import Xtts
from TTS.tts.configs.xtts_config import XttsConfig

from .tts_interface import TTSEngine
from .models import VoiceProfile
from .config import get_settings
from .exceptions import OpenVoiceException

logger = logging.getLogger(__name__)

class XTTSClient(TTSEngine):
    """Cliente XTTS para dublagem e clonagem de voz"""
    
    def __init__(self, device: Optional[str] = None):
        # Inicialização (similar ao F5TTSClient)
        pass
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        **kwargs
    ) -> Tuple[bytes, float]:
        # Implementação XTTS
        pass
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        # Implementação XTTS
        pass
    
    def unload_models(self):
        # Cleanup
        pass
```

**Impacto:** ALTO - Arquivo central da migração

---

### 4.2. Testes XTTS (CRIAR)
**Arquivos novos:**
- `tests/test_xtts_import.py` - Teste de importação
- `tests/test_xtts_basic.py` - Teste de instanciação
- `tests/integration/test_xtts_integration.py` - Teste end-to-end

**Impacto:** MÉDIO - Cobertura de testes

---

### 4.3. Documentação XTTS (CRIAR)
**Arquivos novos:**
- `XTTS-ARCHITECTURE.md` - Arquitetura XTTS no projeto
- `XTTS-USAGE.md` - Guia de uso XTTS
- `MIGRATION-F5TTS-TO-XTTS.md` - Log de migração

**Impacto:** BAIXO - Documentação de referência

---

## 5. PONTOS DE ATENÇÃO E RISCOS

### 5.1. Compatibilidade de API
**Risco:** BAIXO  
**Motivo:** Interface TTSEngine abstrai implementação  
**Mitigação:** Testes end-to-end antes de deploy

---

### 5.2. Performance e VRAM
**Risco:** MÉDIO  
**Comparação:**
- **F5-TTS:** ~2GB VRAM (com lazy loading)
- **XTTS v2:** ~4GB VRAM (modelo maior)

**Mitigação:**
- Testar em ambiente de staging primeiro
- Considerar batch_size=1, use_deepspeed=False
- Monitorar uso de VRAM com `nvidia-smi`

---

### 5.3. Qualidade de Áudio
**Risco:** BAIXO  
**Motivo:** XTTS é production-proven (Coqui TTS)  
**Validação:** Testes comparativos de qualidade antes de deploy

---

### 5.4. Latência de Inferência
**Risco:** BAIXO-MÉDIO  
**Comparação:**
- **F5-TTS:** ~8-10s para clonagem (quando funciona)
- **XTTS v2:** ~5-8s para clonagem + dubbing (streaming <200ms)

**Mitigação:**
- Usar `enable_text_splitting=True` para textos longos
- Considerar streaming para latência <200ms

---

### 5.5. Modelos Pré-treinados
**Risco:** BAIXO  
**Motivo:** XTTS tem modelo pt-BR oficial  
**Download:**
- Modelo: `tts_models/multilingual/multi-dataset/xtts_v2`
- Auto-download via TTS API na primeira execução
- Cache: `/app/models/xtts`

---

### 5.6. Retrocompatibilidade
**Risco:** MÉDIO  
**Pontos críticos:**
- VoiceProfiles existentes no Redis devem continuar funcionando
- Jobs pendentes no Celery devem ser migrados ou cancelados
- Arquivos de áudio clonados devem permanecer válidos

**Mitigação:**
- Migração em janela de manutenção
- Script de migração de VoiceProfiles (se necessário)
- Cancelar jobs pendentes antes do deploy

---

## 6. ESTIMATIVA DE ESFORÇO

### Sprint 1: Preparação (1-2 dias)
- [x] Estudar XTTS (docs, repos, comunidade) - **COMPLETO**
- [x] Criar AUDITORIA.md - **COMPLETO**
- [ ] Criar SPRINTS.md - **PRÓXIMO**
- [ ] Aprovação do plano pelo usuário

### Sprint 2: Implementação Core (3-5 dias)
- [ ] Criar `app/xtts_client.py`
- [ ] Atualizar `requirements.txt` e `Dockerfile`
- [ ] Criar testes unitários XTTS
- [ ] Validar instalação em container

### Sprint 3: Integração (2-3 dias)
- [ ] Modificar `app/processor.py`
- [ ] Modificar `app/config.py`
- [ ] Atualizar `docker-compose.yml`
- [ ] Criar testes de integração

### Sprint 4: Testes e QA (2-3 dias)
- [ ] Testes end-to-end (clonagem + dubbing)
- [ ] Testes de performance (latência, VRAM)
- [ ] Testes de qualidade de áudio
- [ ] Validação em staging

### Sprint 5: Deploy e Cleanup (1-2 dias)
- [ ] Deploy em produção
- [ ] Monitoramento pós-deploy
- [ ] Deletar código F5-TTS obsoleto
- [ ] Atualizar documentação final

**Total:** 9-15 dias (dependendo de complexidade)

---

## 7. CHECKLIST DE MIGRAÇÃO

### Antes da Migração
- [ ] Backup completo do código atual
- [ ] Backup do Redis (VoiceProfiles)
- [ ] Backup do Celery queue
- [ ] Documentar configuração atual F5-TTS
- [ ] Testar XTTS em ambiente isolado

### Durante a Migração
- [ ] Cancelar jobs Celery pendentes
- [ ] Parar serviço audio-voice temporariamente
- [ ] Aplicar mudanças de código
- [ ] Rebuild de imagens Docker
- [ ] Recriar containers com nova config

### Após a Migração
- [ ] Validar health check da API
- [ ] Testar clonagem de voz end-to-end
- [ ] Testar dubbing com voz clonada
- [ ] Monitorar logs por 24-48h
- [ ] Deletar código F5-TTS obsoleto

---

## 8. CONCLUSÃO

### Resumo de Impacto

| Categoria | Arquivos | Impacto | Risco |
|-----------|----------|---------|-------|
| **DELETE** | 15+ arquivos | MÉDIO | BAIXO |
| **MODIFY** | 7 arquivos | ALTO | MÉDIO |
| **UPDATE** | 5 arquivos | MÉDIO | BAIXO |
| **CREATE** | 6 arquivos | ALTO | BAIXO |

### Recomendações Finais

1. **Abordagem TDD:** Criar testes ANTES de implementar XTTS
2. **Migração incremental:** Testar cada sprint isoladamente
3. **Rollback plan:** Manter branch F5-TTS ativa por 2 semanas
4. **Monitoramento:** Logs detalhados nos primeiros 7 dias
5. **Documentação:** Atualizar README e ARCHITECTURE.md ao final

### Próximos Passos

1. ✅ **AUDITORIA.md criado** - Mapeamento completo
2. ⏳ **SPRINTS.md** - Plano detalhado de migração (próximo)
3. ⏳ **Aprovação do usuário** - Apresentar plano para validação
4. ⏳ **Início da execução** - Sprint 1 (apenas após aprovação)

---

**Documento gerado por:** GitHub Copilot  
**Revisão:** Pendente aprovação do usuário  
**Versão:** 1.0  
**Status:** COMPLETO ✅
