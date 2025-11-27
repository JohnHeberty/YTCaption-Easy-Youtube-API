# Sprint 8: Benchmarks PT-BR

## 📋 Visão Geral

Sprint 8 implementa **benchmarking qualitativo** para comparar XTTS vs F5-TTS em português brasileiro.

### Objetivos

1. **MOS Testing** (Mean Opinion Score) - Avaliação humana de qualidade
2. **Comparação Quantitativa** - Métricas objetivas (RTF, VRAM, latência)
3. **Análise PT-BR** - Foco em características do português brasileiro
4. **Recomendações** - Quando usar cada engine

---

## 🎯 Metodologia

### 1. Dataset PT-BR

**Composição:**
- 20 textos variados (curtos, médios, longos)
- 10 vozes de referência (5 masculinas, 5 femininas)
- Cobertura de sotaques brasileiros (SP, RJ, MG, RS, NE)
- Casos de uso: narração, diálogo, podcast, audiobook

### 2. MOS Testing

**Mean Opinion Score (1-5):**
- 1: Péssimo (ininteligível)
- 2: Ruim (inteligível mas com muitos problemas)
- 3: Regular (aceitável, alguns problemas)
- 4: Bom (alta qualidade, poucos problemas)
- 5: Excelente (qualidade profissional)

**Critérios avaliados:**
- **Naturalidade**: Quão natural soa a voz
- **Inteligibilidade**: Clareza e compreensão
- **Prosódia**: Ritmo, entonação, pausas
- **Fidelidade** (cloning): Semelhança com voz original
- **Preferência Geral**: Qual você escolheria?

### 3. Métricas Objetivas

- **RTF** (Real-Time Factor): Velocidade de processamento
- **VRAM**: Uso de memória GPU
- **Latência**: Tempo até primeiro áudio
- **Qualidade de Áudio**: Sample rate, normalização, artefatos

---

## 📊 Estrutura de Arquivos

```
benchmarks/
├── README.md                 # Este arquivo
├── dataset_ptbr.json        # Dataset de teste
├── run_benchmark.py         # Script principal
├── analyze_results.py       # Análise estatística
├── results/
│   ├── xtts_outputs/        # Áudios XTTS
│   ├── f5tts_outputs/       # Áudios F5-TTS
│   ├── metrics.csv          # Métricas quantitativas
│   └── mos_scores.csv       # Scores MOS
└── reports/
    ├── benchmark_report.pdf # Relatório final
    └── visualizations/      # Gráficos comparativos
```

---

## 🚀 Como Executar

### 1. Preparar Dataset

```bash
cd benchmarks
python prepare_dataset.py
```

Isso irá:
- Criar `dataset_ptbr.json` com textos PT-BR
- Baixar vozes de referência (se configurado)
- Validar estrutura do dataset

### 2. Rodar Benchmark

```bash
# Gerar todos os áudios (XTTS + F5-TTS)
python run_benchmark.py --all

# Apenas XTTS
python run_benchmark.py --engine xtts

# Apenas F5-TTS
python run_benchmark.py --engine f5tts

# Com GPU específica
python run_benchmark.py --all --device cuda:0
```

### 3. Coletar MOS Scores

**Opção A: Interface Web (Recomendado)**
```bash
python mos_webapp.py
# Acesse http://localhost:8080
```

**Opção B: Manual CSV**
- Editar `results/mos_scores.csv`
- Adicionar scores para cada áudio

### 4. Analisar Resultados

```bash
python analyze_results.py

# Gera:
# - reports/benchmark_report.pdf
# - reports/visualizations/*.png
# - Estatísticas no terminal
```

---

## 📈 Exemplo de Dataset

```json
{
  "texts": [
    {
      "id": "short_01",
      "text": "Olá, como vai você?",
      "category": "short",
      "use_case": "dialogue"
    },
    {
      "id": "medium_01",
      "text": "O Brasil é um país de dimensões continentais...",
      "category": "medium",
      "use_case": "narration"
    },
    {
      "id": "long_01",
      "text": "Era uma vez, em um reino muito distante...",
      "category": "long",
      "use_case": "audiobook"
    }
  ],
  "voices": [
    {
      "id": "voice_m_sp_01",
      "gender": "male",
      "accent": "sao_paulo",
      "audio_path": "voices/male_sp_01.wav",
      "ref_text": "Esta é uma amostra de voz masculina..."
    }
  ]
}
```

---

## 📊 Métricas Esperadas

### Performance (GPU RTX 3090)

| Engine  | RTF (média) | VRAM (GB) | Latência (s) |
|---------|-------------|-----------|--------------|
| XTTS    | 0.3 - 0.8x  | 2-4 GB    | 3-5s         |
| F5-TTS  | 0.5 - 1.2x  | 3-5 GB    | 5-8s         |

### Qualidade Esperada (MOS)

| Critério        | XTTS | F5-TTS |
|-----------------|------|--------|
| Naturalidade    | 3.8  | 4.2    |
| Inteligibilidade| 4.2  | 4.0    |
| Prosódia        | 3.5  | 4.3    |
| Fidelidade      | 4.0  | 3.8    |
| **Geral**       | **3.9** | **4.1** |

**Nota:** Valores estimados, resultados reais podem variar.

---

## 🎯 Critérios de Aceitação Sprint 8

### Funcional
- [ ] Dataset PT-BR preparado (20 textos + 10 vozes)
- [ ] Script `run_benchmark.py` funcional
- [ ] Áudios gerados (XTTS + F5-TTS)
- [ ] MOS scores coletados (min 5 avaliadores)
- [ ] Análise estatística completa

### Qualidade
- [ ] Cobertura PT-BR representativa
- [ ] Métricas objetivas validadas
- [ ] Análise estatística robusta (t-test, p-value)
- [ ] Visualizações claras

### Documentação
- [ ] README completo
- [ ] Relatório PDF com conclusões
- [ ] Recomendações de uso

---

## ⚠️ Limitações

### Sprint 8 é Semi-Operacional

Diferente dos Sprints 1-7 (100% automatizados), Sprint 8 requer:

1. **Infraestrutura:**
   - GPU para gerar áudios
   - Storage para áudios (pode ser ~1-2GB)

2. **Recursos Humanos:**
   - Painel de avaliadores (5-10 pessoas)
   - Tempo de avaliação (~30min por pessoa)

3. **Dados Reais:**
   - Vozes de referência PT-BR reais
   - Textos representativos

### Alternativa: Benchmark Simplificado

Se recursos limitados, executar versão simplificada:
- 5 textos em vez de 20
- 2 vozes em vez de 10
- Auto-avaliação MOS (1 pessoa)

---

## 📝 Próximos Passos

Após Sprint 8:
- **Sprint 9:** Documentation (README, API docs, migration guide)
- **Sprint 10:** Gradual Rollout (staging, monitoring, production)

---

**Autor:** Sistema F5-TTS Multi-Engine  
**Data:** 27 de Novembro de 2025  
**Sprint:** 8/10 - Benchmarks PT-BR
