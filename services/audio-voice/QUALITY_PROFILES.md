# Quality Profiles - Guia de Uso

## 📋 Visão Geral

O sistema de Quality Profiles permite controlar finamente a qualidade de áudio gerado por cada engine TTS (XTTS e F5-TTS). Existem dois tipos de perfis:

- **🔒 Perfis Padrão (Imutáveis)**: Definidos em código, não podem ser modificados ou deletados
- **✏️ Perfis Customizados**: Criados via API, armazenados no Redis, podem ser editados/deletados

## 🎯 Perfis Padrão XTTS

### `xtts_balanced` ⭐ (Padrão)
**Equilíbrio entre qualidade e velocidade**

```json
{
  "temperature": 0.75,
  "repetition_penalty": 1.5,
  "top_p": 0.9,
  "top_k": 60,
  "length_penalty": 1.2,
  "speed": 1.0,
  "enable_text_splitting": false
}
```

**Quando usar:**
- ✅ Uso geral (90% dos casos)
- ✅ Produção com boa qualidade
- ✅ Latência aceitável (~500ms)

**Características:**
- Estabilidade: 9/10
- Qualidade: 8/10
- Velocidade: Média

---

### `xtts_expressive`
**Máxima expressividade e emoção**

```json
{
  "temperature": 0.85,
  "repetition_penalty": 1.3,
  "top_p": 0.95,
  "top_k": 70,
  "length_penalty": 1.3,
  "speed": 0.98
}
```

**Quando usar:**
- ✅ Conteúdo emocional/dramático
- ✅ Audiolivros com narração expressiva
- ⚠️ Pode ter pequenos artefatos

**Características:**
- Estabilidade: 7/10
- Qualidade: 7.5/10
- Expressividade: 10/10

---

### `xtts_stable`
**Máxima estabilidade para produção em escala**

```json
{
  "temperature": 0.70,
  "repetition_penalty": 1.7,
  "top_p": 0.85,
  "top_k": 55,
  "length_penalty": 1.1,
  "speed": 1.0,
  "enable_text_splitting": true
}
```

**Quando usar:**
- ✅ Produção em larga escala
- ✅ Conteúdo institucional/corporativo
- ✅ Quando consistência é crítica

**Características:**
- Estabilidade: 10/10
- Qualidade: 8.5/10
- Mais rápido (~450ms)

---

## 🎵 Perfis Padrão F5-TTS

### `f5tts_ultra_quality` ⭐ (Padrão)
**Qualidade máxima com redução de chiado**

```json
{
  "nfe_step": 64,
  "cfg_scale": 2.0,
  "denoise_audio": true,
  "noise_reduction_strength": 0.85,
  "apply_deessing": true,
  "deessing_frequency": 7000
}
```

**Quando usar:**
- ✅ Audiolivros e conteúdo premium
- ✅ Quando qualidade > velocidade
- ✅ Vozes com muito chiado/sibilância

**Otimizações Anti-Chiado:**
- ✅ NFE Steps alto (64) para menos artefatos
- ✅ CFG reduzido (2.0) para evitar over-sharpening
- ✅ Denoise agressivo (0.85)
- ✅ De-esser em 7kHz para sibilância
- ✅ Filtros DSP: HPF 50Hz + LPF 12kHz

**Características:**
- Naturalidade: 9.8/10
- Qualidade: 9.5/10
- Latência: ~2.5s
- **Chiado: Muito Reduzido** 🎯

---

### `f5tts_balanced`
**Equilíbrio otimizado para uso geral**

```json
{
  "nfe_step": 40,
  "cfg_scale": 1.8,
  "denoise_audio": true,
  "noise_reduction_strength": 0.75,
  "apply_deessing": true,
  "deessing_frequency": 6500
}
```

**Quando usar:**
- ✅ Uso geral F5-TTS
- ✅ Boa qualidade com velocidade razoável
- ✅ Quando ultra_quality é muito lento

**Otimizações Anti-Chiado:**
- ✅ NFE 40 (bom compromisso)
- ✅ CFG 1.8 (menos sharpening)
- ✅ Denoise moderado (0.75)
- ✅ De-esser ativo

**Características:**
- Naturalidade: 9.0/10
- Qualidade: 8.5/10
- Latência: ~1.7s
- **Chiado: Reduzido** ✅

---

### `f5tts_fast`
**Velocidade mantendo qualidade aceitável**

```json
{
  "nfe_step": 24,
  "cfg_scale": 1.5,
  "denoise_audio": true,
  "noise_reduction_strength": 0.6,
  "apply_deessing": true,
  "deessing_frequency": 6500
}
```

**Quando usar:**
- ✅ Protótipos e testes rápidos
- ✅ Quando velocidade é prioridade
- ⚠️ NFE 24 é o mínimo para qualidade aceitável

**Otimizações Anti-Chiado:**
- ✅ Denoise leve (0.6)
- ✅ De-esser ativo (essencial)
- ⚠️ Pode ter mais chiado que outros perfis

**Características:**
- Naturalidade: 7.8/10
- Qualidade: 7.5/10
- Latência: ~1.0s
- **Chiado: Leve** ⚠️

---

## 🔧 Cadeia de Pós-Processamento F5-TTS

Todos os perfis F5-TTS passam por uma cadeia DSP para reduzir chiado:

```python
1. DC Offset Removal      # Remove componente DC
2. High-Pass @ 50Hz       # Remove rumble sub-bass
3. Wiener Denoise         # Redução de ruído adaptativa
4. De-Esser @ 6-7kHz      # Reduz sibilância (S, SH, CH)
5. Low-Pass @ 12kHz       # Atenua hiss de alta frequência
6. Normalization (-20 LUFS) # Headroom de 5%
```

### Parâmetros Controláveis

| Parâmetro | Range | Padrão | Descrição |
|-----------|-------|--------|-----------|
| `denoise_audio` | bool | true | Ativa/desativa denoise |
| `noise_reduction_strength` | 0.0-1.0 | 0.75 | Força do denoise |
| `apply_deessing` | bool | true | Ativa/desativa de-esser |
| `deessing_frequency` | 4000-10000 | 6500 | Frequência central do de-esser |

---

## 📝 Criar Perfil Customizado

```bash
# Exemplo: perfil F5-TTS para podcast
curl -X POST http://localhost:8005/quality-profiles/f5tts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Podcast Ultra Clean",
    "description": "Otimizado para podcast com máxima redução de chiado",
    "engine": "f5tts",
    "is_default": false,
    "parameters": {
      "nfe_step": 56,
      "cfg_scale": 1.9,
      "speed": 1.0,
      "denoise_audio": true,
      "noise_reduction_strength": 0.9,
      "apply_deessing": true,
      "deessing_frequency": 7500,
      "apply_normalization": true,
      "target_loudness": -16.0
    }
  }'
```

**⚠️ Regras:**
- ❌ Não pode usar IDs reservados: `xtts_*`, `f5tts_*`
- ❌ Não pode marcar como `is_default: true` (use `set-default` depois)
- ✅ Parâmetros específicos do engine
- ✅ Pode editar/deletar depois

---

## 🎛️ Usar Perfil em Job

```bash
# Com perfil padrão
curl -X POST http://localhost:8005/jobs \
  -F "mode=dubbing" \
  -F "text=Olá mundo!" \
  -F "source_language=pt-BR" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=f5tts_ultra_quality"

# Com perfil customizado
curl -X POST http://localhost:8005/jobs \
  -F "mode=dubbing" \
  -F "text=Olá mundo!" \
  -F "source_language=pt-BR" \
  -F "tts_engine=f5tts" \
  -F "quality_profile_id=my_custom_profile"
```

---

## 🚫 Limitações dos Perfis Padrão

### **IMUTÁVEIS - Não podem ser:**
- ❌ Deletados
- ❌ Editados
- ❌ Sobrescritos

### **Tentativas resultam em erro 400:**
```json
{
  "detail": "Perfis padrão são imutáveis e não podem ser atualizados"
}
```

### **Por quê?**
- Garantia de qualidade
- Evita quebrar integrações existentes
- Perfis otimizados pela equipe

---

## 📊 Comparação de Perfis F5-TTS

| Perfil | NFE | CFG | Denoise | De-esser | Latência | Chiado | Uso |
|--------|-----|-----|---------|----------|----------|--------|-----|
| **ultra_quality** | 64 | 2.0 | 0.85 | 7kHz | 2.5s | ⭐⭐⭐⭐⭐ | Premium |
| **balanced** | 40 | 1.8 | 0.75 | 6.5kHz | 1.7s | ⭐⭐⭐⭐ | Geral |
| **fast** | 24 | 1.5 | 0.6 | 6.5kHz | 1.0s | ⭐⭐⭐ | Protótipo |

### Legenda Chiado:
- ⭐⭐⭐⭐⭐ = Muito limpo (quase imperceptível)
- ⭐⭐⭐⭐ = Limpo (leve em transições)
- ⭐⭐⭐ = Aceitável (presente mas controlado)

---

## 🔬 Pesquisa Anti-Chiado F5-TTS

### Causas do Chiado:
1. **Diffusion Noise**: NFE steps baixo deixa ruído residual
2. **Over-sharpening**: CFG alto amplifica artefatos de HF
3. **Sibilância Natural**: Clonagem exagera sons "S", "SH"
4. **HF Artifacts**: Modelo gera ruído >10kHz

### Soluções Implementadas:
1. **↑ NFE Steps**: 32→40/64 (reduz artefatos)
2. **↓ CFG Scale**: 2.5→1.8/2.0 (menos sharpening)
3. **Denoise Agressivo**: Wiener filter 0.75-0.85
4. **De-Esser**: Notch filter 6.5-7kHz
5. **Low-Pass**: Filtro suave @12kHz

### Referências:
- F5-TTS Paper: "Flow Matching in Latent Space"
- Community: Reddit r/LocalLLaMA, HuggingFace Discussions
- Similar: ComfyUI audio workflows, AudioLDM2 denoise

---

## 🆘 FAQ

### P: Posso modificar um perfil padrão?
**R:** Não diretamente. Crie um novo perfil customizado baseado no padrão:

```bash
# 1. Obter perfil padrão
curl http://localhost:8005/quality-profiles/f5tts/f5tts_balanced > base.json

# 2. Editar base.json (mudar ID, name, parameters)

# 3. Criar novo perfil
curl -X POST http://localhost:8005/quality-profiles/f5tts \
  -H "Content-Type: application/json" \
  -d @base.json
```

### P: Como definir perfil customizado como padrão?
```bash
curl -X POST http://localhost:8005/quality-profiles/f5tts/my_profile/set-default
```

### P: F5-TTS ainda tem chiado após otimizações?
**Checklist:**
1. ✅ Usar `f5tts_ultra_quality` ou `balanced`
2. ✅ Áudio de referência limpo (sem ruído de fundo)
3. ✅ Texto com boa pontuação (evita pausas estranhas)
4. ✅ `denoise_audio: true` e `noise_reduction_strength >= 0.75`
5. ✅ `apply_deessing: true`

Se persistir:
- Tente aumentar `noise_reduction_strength` para 0.9
- Aumente `deessing_frequency` para 7500-8000 Hz
- Considere usar RVC para voice conversion adicional

### P: XTTS tem menos chiado que F5-TTS?
**R:** Sim, geralmente. XTTS é mais estável e tem menos artefatos de HF. F5-TTS tem melhor naturalidade mas requer pós-processamento para chiado.

**Recomendação:**
- PT-BR: Use **XTTS** (otimizado, menos chiado)
- Multilíngue/Naturalidade: Use **F5-TTS** com `ultra_quality`

---

## 📚 Recursos Adicionais

- **API Docs**: http://localhost:8005/docs
- **Endpoints**:
  - `GET /quality-profiles` - Listar todos
  - `GET /quality-profiles/{engine}` - Listar por engine
  - `GET /quality-profiles/{engine}/{id}` - Obter específico
  - `POST /quality-profiles/{engine}` - Criar customizado
  - `PATCH /quality-profiles/{engine}/{id}` - Editar customizado
  - `DELETE /quality-profiles/{engine}/{id}` - Deletar customizado
  - `POST /quality-profiles/{engine}/{id}/set-default` - Definir padrão

---

**Última atualização:** 27/11/2025  
**Versão:** 2.0 (Sistema de perfis imutáveis + Anti-chiado F5-TTS)
