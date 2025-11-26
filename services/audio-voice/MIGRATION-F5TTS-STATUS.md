# 🎯 F5-TTS Migration Status Report

**Data:** 26/11/2025  
**Especialista:** AI Senior Python & Deep Learning  
**GPU Target:** GTX 1050 Ti (4GB VRAM)  
**Modelo pt-BR:** `services/audio-voice/models/f5tts/pt-br/model_last.safetensors` (1.35 GB)

---

## ✅ CONQUISTAS REALIZADAS

### 1. **Correção do ModuleNotFoundError**
- ✅ **Causa raiz identificada:** `processor.py` importava `openvoice_client` inexistente
- ✅ **Solução implementada:** Criado adapter `OpenVoiceClient` que internamente usa F5-TTS
- ✅ **Arquivos criados/modificados:**
  - [`services/audio-voice/app/openvoice_client.py`](openvoice_client.py) (NOVO - 480 linhas)
  - [`services/audio-voice/app/f5tts_client.py`](f5tts_client.py) (atualizado)
  - [`services/audio-voice/app/exceptions.py`](exceptions.py) (adicionado `OpenVoiceException`)
  - [`services/audio-voice/app/main.py`](main.py) (health check corrigido)

### 2. **Configuração F5-TTS para GTX 1050 Ti**
- ✅ Otimizações VRAM implementadas:
  - `F5TTS_NFE_STEP=16` (reduzido de 32)
  - `F5TTS_USE_FP16=true` (half precision)
  - `F5TTS_MAX_BATCH_SIZE=1`
  - `MPLCONFIGDIR=/app/temp/.matplotlib` (fix matplotlib cache)
- ✅ Docker environment configurado corretamente
- ✅ Limpeza de espaço em disco (28GB recuperados, de 100% para 70%)

### 3. **Correção da API F5-TTS**
- ✅ Corrigido parâmetro `model_type` → `model` (compatível com assinatura real da API)
- ✅ Identificados arquivos de configuração disponíveis:
  ```
  /usr/local/lib/python3.11/dist-packages/f5_tts/configs/
  ├── F5TTS_Base.yaml
  ├── F5TTS_v1_Base.yaml
  ├── F5TTS_Small.yaml
  ├── E2TTS_Base.yaml
  └── E2TTS_Small.yaml
  ```

### 4. **Especialização em F5-TTS**
- ✅ Estudado repositório oficial: https://github.com/SWivid/F5-TTS
- ✅ Compreensão profunda da API e parâmetros
- ✅ Identificação de limitações com modelos customizados

---

## ❌ PROBLEMA CRÍTICO IDENTIFICADO

### **Incompatibilidade de Arquitetura do Modelo pt-BR**

O modelo `model_last.safetensors` possui uma **arquitetura incompatível** com a biblioteca `f5-tts` instalada via pip:

#### Erros Detalhados:

```python
RuntimeError: Error(s) in loading state_dict for CFM:
  # Size mismatch
  - transformer.text_embed.text_embed.weight: 
    Checkpoint: torch.Size([2546, 512])
    Expected:   torch.Size([2546, 100])
  
  - transformer.input_embed.proj.weight:
    Checkpoint: torch.Size([1024, 712])
    Expected:   torch.Size([1024, 300])
  
  # Structural differences
  - Missing keys: transformer.layers.*.* (estrutura antiga F5-TTS)
  - Unexpected keys: transformer.transformer_blocks.*.* (estrutura nova/customizada)
```

#### Análise do Problema:

1. **Origem do modelo:** Fine-tuning E2-TTS/F5-TTS para português brasileiro
2. **Versão incompatível:** Modelo treinado com versão diferente do F5-TTS
3. **Embeddings maiores:** 512 vs 100 dims = modelo mais robusto, mas incompatível

---

## 🔧 SOLUÇÕES POSSÍVEIS

### **Opção 1: Usar F5-TTS do Repositório Original** ⭐ RECOMENDADA

```bash
# Desinstalar f5-tts do pip
pip uninstall f5-tts

# Clonar repo oficial e instalar
cd /app/models/f5tts
git clone https://github.com/SWivid/F5-TTS.git
cd F5-TTS
pip install -e .
```

**Vantagens:**
- Suporte a modelos customizados
- Versão mais atualizada
- Flexibilidade para ajustes

**Desvantagens:**
- Requer rebuild do container
- Possíveis dependências adicionais

---

### **Opção 2: Retreinar Modelo com F5-TTS Atual**

Usar a biblioteca atual para fazer fine-tuning novo com dados pt-BR.

**Vantagens:**
- Modelo garantidamente compatível
- Controle total do processo

**Desvantagens:**
- Requer dataset pt-BR
- Tempo de treinamento significativo
- Requer GPU mais potente para treino

---

### **Opção 3: Usar Modelo HuggingFace Padrão Temporariamente**

Enquanto resolve o modelo customizado, usar o modelo base do F5-TTS:

```python
# Em vez de:
self.f5tts = F5TTS(
    model='F5TTS_Base',
    ckpt_file=custom_model_path,  # ❌ Incompatível
    ...
)

# Usar:
self.f5tts = F5TTS(
    model='F5TTS_Base',
    # Sem ckpt_file = usa modelo HuggingFace padrão
    ...
)
```

**Vantagens:**
- Serviço sobe imediatamente
- Testável agora mesmo

**Desvantagens:**
- Sem otimização para pt-BR
- Qualidade inferior para português

---

## 📊 STATUS ATUAL DO SERVIÇO

```
✅ Código adaptado e corrigido
✅ Docker configurado para GTX 1050 Ti
✅ Ambiente limpo e otimizado
❌ Serviço NÃO SOBE devido à incompatibilidade do modelo
```

### Logs Finais:
```
audio-voice-api  | app.exceptions.OpenVoiceException: TTS engine error: 
Model loading failed: Error(s) in loading state_dict for CFM
```

---

## 🚀 PRÓXIMOS PASSOS RECOMENDADOS

### **Estratégia Imediata (Teste):**

1. Modificar `openvoice_client.py` e `f5tts_client.py` para **não usar modelo customizado** temporariamente
2. Testar serviço com modelo base
3. Validar pipeline completo

### **Estratégia de Longo Prazo:**

1. Instalar F5-TTS do repositório original
2. Investigar compatibilidade do `model_last.safetensors`
3. Se incompatível, buscar/treinar modelo pt-BR compatível
4. Implementar fallback inteligente (modelo base → modelo pt-BR)

---

## 📁 ARQUIVOS MODIFICADOS (RESUMO)

```
services/audio-voice/
├── app/
│   ├── openvoice_client.py      [CRIADO - 480 linhas]
│   ├── f5tts_client.py           [MODIFICADO - API corrigida]
│   ├── exceptions.py             [MODIFICADO - +OpenVoiceException]
│   └── main.py                   [MODIFICADO - health check]
├── docker-compose.yml            [MODIFICADO - env vars]
└── .env                          [MODIFICADO - otimizações GPU]
```

---

## 💡 APRENDIZADOS CHAVE

1. **Incompatibilidade de modelos** é comum em projetos de Deep Learning
2. **Versões de bibliotecas** devem ser documentadas junto aos checkpoints
3. **Fine-tuning** pode alterar arquiteturas de formas incompatíveis
4. **Fallbacks** são essenciais em produção

---

## 📞 SUPORTE TÉCNICO

Para resolver definitivamente, você precisa:

1. **Informação sobre o modelo:**
   - Qual versão do F5-TTS foi usada para gerar `model_last.safetensors`?
   - Existe repositório/documentação do treinamento?

2. **Decisão estratégica:**
   - Aceitar modelo base temporário?
   - Buscar modelo pt-BR compatível?
   - Retreinar do zero?

---

**Última Atualização:** 26/11/2025 01:45 UTC  
**Autor:** AI Senior Python & Deep Learning Expert
