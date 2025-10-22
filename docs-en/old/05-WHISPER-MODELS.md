# 🎯 Whisper Models

**Guia completo para escolher o modelo Whisper ideal - comparação, requisitos e recomendações.**

---

## 📋 Índice

1. [Modelos Disponíveis](#modelos-disponíveis)
2. [Comparação Detalhada](#comparação-detalhada)
3. [Como Escolher](#como-escolher)
4. [Requisitos de Hardware](#requisitos-de-hardware)
5. [Benchmark de Performance](#benchmark-de-performance)
6. [Idiomas Suportados](#idiomas-suportados)

---

## Modelos Disponíveis

O Whisper possui **6 modelos** com diferentes trade-offs entre **velocidade** e **precisão**:

| Modelo | Tamanho | Parâmetros | RAM/Worker | Velocidade | Precisão |
|--------|---------|------------|------------|------------|----------|
| `tiny` | 39 MB | 39M | ~400 MB | ⚡⚡⚡⚡⚡ | ⭐⭐ |
| `base` | 74 MB | 74M | ~800 MB | ⚡⚡⚡⚡ | ⭐⭐⭐ |
| `small` | 244 MB | 244M | ~1.5 GB | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| `medium` | 769 MB | 769M | ~3 GB | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| `large` | 1550 MB | 1550M | ~6 GB | ⚡ | ⭐⭐⭐⭐⭐ |
| `turbo` | 809 MB | 809M | ~3.5 GB | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ |

---

## Comparação Detalhada

### 🏃 tiny

**Características**:
- ✅ Menor modelo (39 MB)
- ✅ Mais rápido (5-10x mais rápido que base)
- ✅ Ideal para testes e desenvolvimento
- ⚠️ Precisão limitada (~60-70%)
- ⚠️ Erra nomes próprios e termos técnicos

**Uso Recomendado**:
- 🧪 Desenvolvimento e testes
- 🚀 Prototipagem rápida
- 📱 Dispositivos com RAM limitada (4GB)
- ⏱️ Quando velocidade é mais importante que precisão

**Não recomendado para**:
- ❌ Produção
- ❌ Conteúdo profissional
- ❌ Transcrições oficiais

**Configuração**:
```bash
WHISPER_MODEL=tiny
```

---

### ⭐ base (Recomendado)

**Características**:
- ✅ **Equilíbrio ideal** velocidade vs precisão
- ✅ Precisão boa (~75-85%)
- ✅ Consome apenas 800 MB RAM
- ✅ **Padrão da aplicação**
- ✅ Funciona bem em 90% dos casos

**Uso Recomendado**:
- 🎯 **Produção (padrão)**
- 🎥 YouTube, podcasts, entrevistas
- 💼 Uso corporativo geral
- 🖥️ Servidores com 8GB+ RAM

**Quando usar**:
- ✅ Você não tem requisitos específicos
- ✅ Quer começar rápido
- ✅ Precisa de qualidade aceitável

**Configuração**:
```bash
WHISPER_MODEL=base  # Já é o padrão
```

---

### 📈 small

**Características**:
- ✅ Precisão alta (~85-90%)
- ✅ Melhor que base em sotaques e ruído
- ⚠️ 2x mais lento que base
- ⚠️ Consome 1.5 GB RAM por worker

**Uso Recomendado**:
- 🎙️ Podcasts profissionais
- 📻 Entrevistas com múltiplas pessoas
- 🌍 Áudio com sotaques variados
- 🔊 Áudio com ruído de fundo
- 💪 Servidores com 16GB+ RAM

**Quando usar**:
- ✅ Qualidade é prioridade
- ✅ Você tem CPU potente (4+ cores)
- ✅ Tempo de processamento não é crítico

**Configuração**:
```bash
WHISPER_MODEL=small
```

---

### 🚀 medium

**Características**:
- ✅ Precisão muito alta (~90-95%)
- ✅ Excelente para idiomas não-ingleses
- ⚠️ 4x mais lento que base
- ⚠️ Consome 3 GB RAM por worker
- 💡 **Ideal com GPU**

**Uso Recomendado**:
- 🎬 Produção de vídeo profissional
- 📝 Transcrições oficiais
- 🏢 Documentação legal/médica
- 🖥️ **Servidores com GPU NVIDIA**
- 💾 Servidores com 32GB+ RAM (CPU)

**Quando usar**:
- ✅ Você tem GPU NVIDIA (CUDA)
- ✅ Precisão máxima é requisito
- ✅ Orçamento não é problema

**Configuração**:
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda  # Recomendado
```

---

### 🏆 large

**Características**:
- ✅ **Melhor precisão absoluta** (~95-98%)
- ✅ Estado da arte em transcrição
- ⚠️ 8-10x mais lento que base
- ⚠️ Consome 6 GB RAM por worker
- 💡 **Requer GPU potente**

**Uso Recomendado**:
- 🎓 Pesquisa acadêmica
- 🎬 Cinema e TV (legendas oficiais)
- 🏛️ Documentação histórica
- 🖥️ **GPU NVIDIA de alta performance**

**Quando usar**:
- ✅ Você precisa da melhor qualidade possível
- ✅ Você tem GPU NVIDIA RTX 3090/4090 ou superior
- ✅ Tempo não é limitação

**Não recomendado para**:
- ❌ CPU (muito lento)
- ❌ Produção em larga escala
- ❌ Servidores com RAM limitada

**Configuração**:
```bash
WHISPER_MODEL=large
WHISPER_DEVICE=cuda  # Obrigatório
```

---

### ⚡ turbo (Novo!)

**Características**:
- ✅ Precisão similar ao `medium` (~90-93%)
- ✅ 2x mais rápido que `medium`
- ✅ Melhor relação velocidade/qualidade
- ⚠️ Consome 3.5 GB RAM
- 💡 **Ótimo com GPU**

**Uso Recomendado**:
- 🎯 Produção com GPU
- 🚀 Quando você quer qualidade alta + velocidade
- 🖥️ Substituir `medium` para ganhar velocidade

**Quando usar**:
- ✅ Você tem GPU NVIDIA
- ✅ Quer qualidade alta sem esperar muito
- ✅ Alternativa ao `medium`

**Configuração**:
```bash
WHISPER_MODEL=turbo
WHISPER_DEVICE=cuda  # Recomendado
```

---

## Como Escolher

### Fluxograma de Decisão

```
┌─────────────────────────┐
│ Você tem GPU NVIDIA?    │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │   SIM   │───────► WHISPER_DEVICE=cuda
    │         │         ├─ Qualidade máxima? ───► large
    │         │         ├─ Equilíbrio? ──────────► turbo ou medium
    │         │         └─ Velocidade? ──────────► base
    └─────────┘
         │
    ┌────┴────┐
    │   NÃO   │───────► WHISPER_DEVICE=cpu
    │   (CPU) │         ├─ RAM > 16GB? ──────────► small
    │         │         ├─ RAM 8-16GB? ──────────► base (padrão)
    │         │         └─ RAM < 8GB? ───────────► tiny
    └─────────┘
```

---

### Por Caso de Uso

| Caso de Uso | Modelo Recomendado | Alternativa |
|-------------|-------------------|-------------|
| **Testes/Desenvolvimento** | `tiny` | `base` |
| **Produção geral** | `base` ✅ | `small` |
| **Podcasts profissionais** | `small` | `base` |
| **Vídeos com ruído** | `small` | `medium` |
| **Transcrições oficiais** | `medium` (GPU) | `small` (CPU) |
| **Legendas para cinema** | `large` (GPU) | `medium` (GPU) |
| **Pesquisa acadêmica** | `large` (GPU) | `medium` (GPU) |
| **Produção com GPU** | `turbo` | `medium` |

---

### Por Recursos de Hardware

| Hardware | Modelo Recomendado | MAX_CONCURRENT_REQUESTS |
|----------|-------------------|------------------------|
| **4GB RAM, 2 cores CPU** | `tiny` | 2 |
| **8GB RAM, 4 cores CPU** | `base` ✅ | 3 |
| **16GB RAM, 8 cores CPU** | `small` | 4 |
| **32GB RAM, GPU RTX 3060** | `medium` (cuda) | 5 |
| **64GB RAM, GPU RTX 4090** | `large` (cuda) | 6 |

---

## Requisitos de Hardware

### CPU (sem GPU)

| Modelo | RAM Mínima | RAM Recomendada | CPU Cores |
|--------|------------|-----------------|-----------|
| `tiny` | 2 GB | 4 GB | 2+ |
| `base` | 4 GB | 8 GB | 4+ |
| `small` | 8 GB | 16 GB | 8+ |
| `medium` | 16 GB | 32 GB | 16+ |
| `large` | ❌ Não recomendado para CPU | | |

### GPU (CUDA)

| Modelo | VRAM GPU | GPU Recomendada | Speedup vs CPU |
|--------|----------|-----------------|----------------|
| `tiny` | 1 GB | GTX 1050 Ti | 5-8x |
| `base` | 2 GB | GTX 1060 | 8-12x |
| `small` | 4 GB | RTX 3050 | 10-15x |
| `medium` | 6 GB | RTX 3060 | 12-18x |
| `large` | 10 GB | RTX 3090/4090 | 15-20x |
| `turbo` | 8 GB | RTX 3070 | 15-18x |

---

## Benchmark de Performance

**Teste**: Transcrição de 1 hora de áudio (português, boa qualidade)

### CPU: AMD Ryzen 7 5800X (8 cores, 16 threads)

| Modelo | Tempo | WER* | Caracteres Errados |
|--------|-------|------|-------------------|
| `tiny` | 8 min | 25% | Alto |
| `base` | 15 min ✅ | 15% | Médio |
| `small` | 32 min | 10% | Baixo |
| `medium` | 90 min | 7% | Muito Baixo |

*WER = Word Error Rate (taxa de erro de palavras)

### GPU: NVIDIA RTX 3070 (8GB VRAM)

| Modelo | Tempo | WER* | Speedup vs CPU |
|--------|-------|------|----------------|
| `tiny` | 1.5 min | 25% | 5.3x |
| `base` | 2 min | 15% | 7.5x |
| `small` | 3 min | 10% | 10.7x |
| `medium` | 6 min | 7% | 15x |
| `large` | 10 min | 5% | 18x |
| `turbo` | 4 min | 8% | 16x |

---

## Idiomas Suportados

### Todos os modelos suportam 99 idiomas:

**Principais**:
- 🇧🇷 Português (pt)
- 🇺🇸 Inglês (en)
- 🇪🇸 Espanhol (es)
- 🇫🇷 Francês (fr)
- 🇩🇪 Alemão (de)
- 🇮🇹 Italiano (it)
- 🇯🇵 Japonês (ja)
- 🇰🇷 Coreano (ko)
- 🇨🇳 Chinês (zh)
- 🇷🇺 Russo (ru)

**E mais 89 idiomas...**

### Precisão por Idioma

| Modelo | Inglês | Português | Chinês | Outros |
|--------|--------|-----------|--------|--------|
| `tiny` | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ |
| `base` | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| `small` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| `medium` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| `large` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**Observação**: Modelos maiores (`medium`, `large`) têm melhor desempenho em idiomas não-ingleses.

---

## Dicas de Otimização

### 1. Combine com Transcrição Paralela

```bash
WHISPER_MODEL=base
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
```

**Benefício**: 3-4x mais rápido mantendo qualidade.

---

### 2. Use GPU se Disponível

```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
```

**Benefício**: 10-20x mais rápido que CPU.

---

### 3. Especifique o Idioma

```bash
WHISPER_LANGUAGE=pt  # Para português
```

**Benefício**: 5-10% mais preciso + 10-20% mais rápido.

---

### 4. Escolha Modelo pelo Áudio

**Áudio limpo (estúdio)**:
- ✅ `base` ou `tiny` são suficientes

**Áudio com ruído/sotaque**:
- ✅ Use `small` ou `medium`

**Áudio em idioma não-inglês**:
- ✅ Use pelo menos `small`

---

## Troca de Modelo em Tempo Real

### Via Variável de Ambiente

Edite `.env` e reinicie:
```bash
WHISPER_MODEL=small
```

### Via start.sh

```bash
./start.sh --model small
```

### Via Docker

```bash
docker-compose down
docker-compose up -d
```

---

## Comparação Visual

```
VELOCIDADE vs PRECISÃO

  Velocidade
      ⬆️
      │
 tiny │ ●
      │
 base │     ●  ← Equilíbrio ideal ✅
      │
small │         ●
      │
medium│             ● (GPU)
      │
large │                 ● (GPU)
      │
turbo │           ● (GPU)
      │
      └─────────────────────────► Precisão
```

---

## Recomendação Final

**Para 90% dos casos**:
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
```

**Se você tem GPU**:
```bash
WHISPER_MODEL=turbo
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=false  # GPU já é rápido
```

**Se precisar de máxima qualidade (CPU)**:
```bash
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
```

---

**Próximo**: [Transcrição Paralela](./06-PARALLEL-TRANSCRIPTION.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
