# 🎯 Como Usar os Resultados do Teste

## Arquivos Gerados

O teste cria automaticamente 4 arquivos essenciais em `tests/output_clone_analysis/`:

### 1. `analysis_results_<timestamp>.json`
**O que é**: Dados brutos completos em formato JSON  
**Uso**: Importar em scripts Python, análise programática, tracking histórico

**Estrutura**:
```json
{
  "timestamp": "2025-11-25T05:42:38",
  "test_audio": "/app/tests/Teste.mp3",
  "original": {
    "spectral": { "spectral_centroid": 722.1, "top_frequencies": [...] },
    "formants": { "F1": {"mean": 677.2, "std": 5.6}, ... },
    "prosody": { "pitch": {"mean": 177.2}, "energy": {...} }
  },
  "cloned": { ... },
  "comparison": {
    "spectral_centroid_error_%": 112.29,
    "spectral_rolloff_error_%": 73.23
  }
}
```

**Como usar**:
```python
import json

with open('analysis_results_20251125_054238.json') as f:
    data = json.load(f)

error = data['comparison']['spectral_centroid_error_%']
print(f"Erro do centróide espectral: {error:.1f}%")

# Histórico de melhorias
errors = []
for file in glob('analysis_results_*.json'):
    with open(file) as f:
        errors.append(json.load(f)['comparison']['spectral_centroid_error_%'])
plot_improvement(errors)
```

---

### 2. `cloned_audio.wav`
**O que é**: Áudio gerado pela IA (clone da sua voz)  
**Uso**: Ouvir resultado, comparar com original

**Como usar**:
```bash
# Tocar áudio
play cloned_audio.wav
# ou
mpv cloned_audio.wav
# ou
vlc cloned_audio.wav

# Ver informações
soxi cloned_audio.wav

# Comparar lado a lado
play tests/Teste.mp3 cloned_audio.wav
```

**Análise manual**:
1. Ouça: Parece com sua voz?
2. Compare prosódia: Entonação, ritmo, pausas
3. Verifique qualidade: Ruído, artefatos, clareza
4. Teste inteligibilidade: Consegue entender as palavras?

---

### 3. `comparison_plots_<timestamp>.png`
**O que é**: 6 gráficos comparando original vs clone  
**Uso**: Análise visual rápida

**Gráficos inclusos**:

```
┌─────────────────────┬─────────────────────┐
│  Original Waveform  │  Cloned Waveform    │ ← Forma de onda
├─────────────────────┼─────────────────────┤
│ Original Spectrogram│ Cloned Spectrogram  │ ← Frequência x tempo
├─────────────────────┼─────────────────────┤
│ Original Spectrum   │ Cloned Spectrum     │ ← FFT (amplitude x freq)
└─────────────────────┴─────────────────────┘
```

**Como interpretar**:

**Waveform (forma de onda)**:
- ✅ Esperado: Variação irregular, densidade variável
- ❌ Problema: Padrão repetitivo regular = beep

**Spectrogram**:
- ✅ Esperado: Bandas horizontais em múltiplas frequências (formantes)
- ❌ Problema: Linha horizontal única = tom puro

**Frequency Spectrum**:
- ✅ Esperado: Picos distribuídos (fundamental + harmonics + formantes)
- ❌ Problema: Pico gigante único = concentração anormal

**Abrir**:
```bash
# Linux
xdg-open comparison_plots_20251125_054239.png
eog comparison_plots_20251125_054239.png

# VS Code
code comparison_plots_20251125_054239.png
```

---

### 4. `TEST-RESULTS-ANALYSIS.md`
**O que é**: Relatório completo em linguagem humana  
**Uso**: Entender problema sem conhecimento técnico

**Seções**:
- **Critical Findings**: O que está errado
- **Quantitative Analysis**: Números e tabelas
- **Root Cause**: Por que está acontecendo
- **Recommended Fixes**: Como corrigir
- **Validation Criteria**: Quando considerar resolvido

**Como usar**: Leia de cima pra baixo, compartilhe com equipe

---

## Workflows Práticos

### Workflow 1: Debug Rápido
"Os áudios estão ruins, preciso saber o que está errado"

```bash
# 1. Roda teste
./run_clone_test.sh

# 2. Olha o relatório no terminal (última seção)
# Mostra erro % das principais métricas

# 3. Ouve o clone
play tests/output_clone_analysis/cloned_audio.wav

# 4. Se precisar mais detalhes
cat tests/output_clone_analysis/TEST-RESULTS-ANALYSIS.md
```

**Tempo**: 2-3 minutos

---

### Workflow 2: Análise Profunda
"Preciso entender exatamente qual frequência está problemática"

```bash
# 1. Roda teste
./run_clone_test.sh

# 2. Abre gráficos
xdg-open tests/output_clone_analysis/comparison_plots_*.png

# 3. Lê JSON para valores exatos
cat tests/output_clone_analysis/analysis_results_*.json | jq '
  .original.spectral.top_frequencies[0:5],
  .cloned.spectral.top_frequencies[0:5]
'

# 4. Compara formantes
cat tests/output_clone_analysis/analysis_results_*.json | jq '
  .original.formants,
  .cloned.formants
'
```

**Tempo**: 10-15 minutos

---

### Workflow 3: Tracking de Melhorias
"Fiz mudanças no código, melhorou?"

```bash
# 1. Baseline (antes)
./run_clone_test.sh
mv tests/output_clone_analysis tests/output_baseline

# 2. Implementa mudanças
vim app/openvoice_client.py
docker compose build --no-cache
docker compose up -d

# 3. Testa novo código
./run_clone_test.sh

# 4. Compara métricas
echo "=== BEFORE ==="
cat tests/output_baseline/analysis_results_*.json | jq '.comparison'

echo "=== AFTER ==="
cat tests/output_clone_analysis/analysis_results_*.json | jq '.comparison'

# 5. Compara áudio
play tests/output_baseline/cloned_audio.wav tests/output_clone_analysis/cloned_audio.wav
```

**Tempo**: 5-10 minutos (após mudanças)

---

### Workflow 4: Automação CI/CD
"Quero rodar teste automaticamente no pipeline"

```yaml
# .github/workflows/voice-quality.yml
name: Voice Quality Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run voice clone test
        run: |
          cd services/audio-voice
          ./run_clone_test.sh
      
      - name: Check quality threshold
        run: |
          ERROR=$(jq -r '.comparison.spectral_centroid_error_%' \
            tests/output_clone_analysis/analysis_results_*.json)
          
          if (( $(echo "$ERROR > 30" | bc -l) )); then
            echo "❌ Quality regression! Error: ${ERROR}%"
            exit 1
          fi
          echo "✅ Quality OK! Error: ${ERROR}%"
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: voice-analysis
          path: services/audio-voice/tests/output_clone_analysis/
```

---

## Interpretação de Resultados

### Quando o teste PASSA ✅

```
Spectral Centroid Error: 8.5%      ← < 20% ✅
Spectral Rolloff Error: 12.3%      ← < 25% ✅
Formants Detected: F1=710 F2=1250 F3=2800 ✅
Pitch Error: 18 Hz                 ← < 30 Hz ✅
Energy Ratio: 0.95                 ← 0.8-1.2 ✅

Score: 100% - EXCELLENT ⭐⭐⭐⭐⭐
```

**O que fazer**: Deploy para produção!

---

### Quando o teste FALHA ❌

```
Spectral Centroid Error: 112%      ← WAY too high! ❌
Formants Detected: None            ← Missing! ❌
Energy Ratio: 14.8                 ← Clipping! ❌

Score: 0% - CRITICAL FAILURE 💥
```

**O que fazer**:
1. Leia `TEST-RESULTS-ANALYSIS.md` seção "Root Cause"
2. Veja `comparison_plots_*.png` para validar visualmente
3. Ouça `cloned_audio.wav` (deve soar como beep)
4. Implemente correções sugeridas
5. Re-rode teste para validar

---

## Métricas - Guia Rápido

### Spectral Centroid
- **O que é**: "Centro de gravidade" do espectro
- **Normal**: 500-1500 Hz para voz
- **Se muito alto**: Som muito "agudo/metálico"
- **Se muito baixo**: Som "abafado/grave demais"

### Spectral Rolloff
- **O que é**: Freq abaixo da qual está 85% da energia
- **Normal**: 800-2000 Hz
- **Se muito alto**: Muita energia em altas frequências (chiado)
- **Se muito baixo**: Falta de clareza

### Spectral Flatness
- **O que é**: Quão "ruidoso" vs "tonal"
- **0.0**: Tom puro (beep)
- **0.5**: Meio termo
- **1.0**: Ruído branco
- **Voz normal**: 0.02 - 0.15

### Formants (F1, F2, F3)
- **O que são**: Ressonâncias do trato vocal
- **F1** (300-1000 Hz): Abertura da boca
- **F2** (800-2500 Hz): Posição da língua
- **F3** (2000-4000 Hz): Arredondamento dos lábios
- **Se não detectados**: Não tem qualidade de vogal

### Pitch (F0)
- **O que é**: Frequência fundamental (tom da voz)
- **Homem**: ~100-150 Hz
- **Mulher**: ~180-250 Hz
- **Se muito diferente**: Muda identidade vocal

### Energy (RMS)
- **O que é**: Volume/amplitude
- **Se muito alto**: Distorção/clipping
- **Se muito baixo**: Áudio fraco
- **Ideal**: Ratio 0.8-1.2 (clone vs original)

---

## Exportar Resultados

### Para relatório em Word/PDF

```bash
# Converte Markdown para PDF
pandoc TEST-RESULTS-ANALYSIS.md -o report.pdf

# Ou HTML
pandoc TEST-RESULTS-ANALYSIS.md -o report.html
```

### Para apresentação

```python
import json
import matplotlib.pyplot as plt

# Carrega dados
with open('analysis_results_20251125_054238.json') as f:
    data = json.load(f)

# Gráfico de barras
metrics = ['Spectral\nCentroid', 'Spectral\nRolloff', 'Pitch']
original = [
    data['original']['spectral']['spectral_centroid'],
    data['original']['spectral']['spectral_rolloff'],
    data['original']['prosody']['pitch']['mean']
]
cloned = [
    data['cloned']['spectral']['spectral_centroid'],
    data['cloned']['spectral']['spectral_rolloff'],
    data['cloned']['prosody']['pitch']['mean']
]

x = range(len(metrics))
plt.bar([i-0.2 for i in x], original, width=0.4, label='Original', color='green')
plt.bar([i+0.2 for i in x], cloned, width=0.4, label='Cloned', color='red')
plt.xticks(x, metrics)
plt.ylabel('Hz')
plt.legend()
plt.title('Voice Clone Quality Comparison')
plt.savefig('presentation_chart.png', dpi=150)
```

---

## Troubleshooting

### "Não consigo ouvir o áudio"

```bash
# Instala player
sudo apt install sox mpv

# Verifica arquivo
file cloned_audio.wav
soxi cloned_audio.wav

# Se corrompido, regenera
./run_clone_test.sh
```

### "Gráficos não abrem"

```bash
# Instala visualizador
sudo apt install eog feh

# Ou copia para local
cp comparison_plots_*.png ~/Desktop/
```

### "JSON muito grande pra ler"

```bash
# Usa jq para filtrar
jq '.comparison' analysis_results_*.json

# Somente top 5 frequências
jq '.original.spectral.top_frequencies[0:5]' analysis_results_*.json
```

---

## Dicas Avançadas

### Comparar múltiplos testes

```bash
# Extrai erro de todos testes
for f in analysis_results_*.json; do
    echo "$f: $(jq -r '.comparison.spectral_centroid_error_%' $f)%"
done | sort -t: -k2 -n
```

### Gerar heatmap de formantes

```python
import json
import seaborn as sns
import matplotlib.pyplot as plt

# Carrega múltiplos resultados
results = []
for file in glob('analysis_results_*.json'):
    with open(file) as f:
        results.append(json.load(f))

# Matriz de formantes
formants = [[r['original']['formants'][f]['mean'] for f in ['F1','F2','F3']]
            for r in results]

sns.heatmap(formants, annot=True, fmt='.0f', cmap='RdYlGn_r')
plt.xlabel('Formant')
plt.ylabel('Test Run')
plt.title('Formant Stability Across Tests')
plt.show()
```

---

**Dúvidas?** Veja `tests/README-CLONE-TEST.md` para documentação completa.
