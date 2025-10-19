# 🧪 Benchmark: Transcrição Paralela vs Single-Core

Documentação dos scripts de teste e benchmark para comparar a performance da transcrição paralela por chunks vs transcrição tradicional single-core.

---

## 📁 Arquivos

### 1. `whisper_parallel_service.py`
**Implementação da transcrição paralela**

- Classe: `WhisperParallelTranscriptionService`
- Divide áudio em chunks (padrão: 120 segundos)
- Usa `ProcessPoolExecutor` para transcrever chunks em paralelo
- Merge automático de segmentos com ajuste de timestamps
- Detecção de idioma via votação (mais comum entre chunks)

**Características técnicas:**
- Multiprocessing real (bypassa GIL do Python)
- Cada worker carrega modelo Whisper independente
- Normalização de áudio FFmpeg
- Error handling por chunk
- Cleanup automático de arquivos temporários

---

### 2. `download_test_video.py`
**Script auxiliar para baixar vídeo de teste**

**Uso:**
```bash
# Usar URL padrão (vídeo curto de exemplo)
python teste_melhoria/download_test_video.py

# Especificar URL customizada
python teste_melhoria/download_test_video.py "https://youtube.com/watch?v=VIDEO_ID"
```

**Saída:**
- Arquivo: `./temp/test_video.mp3`
- Formato: MP3 (melhor qualidade)
- Usa yt-dlp para download

**Requisito:**
```bash
pip install yt-dlp
```

---

### 3. `benchmark_parallel_transcription.py`
**Comparação completa: Single-core vs Multi-core**

**Funcionalidade:**
- Testa método atual (single-threaded)
- Testa método paralelo (multi-process chunks)
- Compara tempos, qualidade, idioma detectado
- Gera relatório detalhado com speedup

**Uso:**
```bash
python teste_melhoria/benchmark_parallel_transcription.py
```

**Requisitos:**
- Vídeo de teste em `./temp/test_video.mp3`
- Configurar `NUM_WORKERS` no script (padrão: 4)

**Output esperado:**
```
⏱️  TIME COMPARISON:
  Single-core: 120.50s
  Multi-core:  38.20s (4 workers)
  Speedup:     3.15x
  Improvement: 68.3% faster

📝 QUALITY COMPARISON:
  Single-core segments: 245
  Multi-core segments:  243
  Difference:           2 segments (0.8%)

🌍 LANGUAGE DETECTION:
  Single-core: pt
  Multi-core:  pt
  Match:       ✅ YES
```

---

### 4. `test_multi_workers.py`
**Teste rápido com múltiplas configurações de workers**

**Funcionalidade:**
- Testa automaticamente: 1, 2, 4, 8 workers
- Gera tabela comparativa de performance
- Calcula eficiência de cada configuração
- Identifica melhor configuração

**Uso:**
```bash
python teste_melhoria/test_multi_workers.py
```

**Output esperado:**
```
📊 RESULTS COMPARISON
┌────────────┬────────────┬──────────────┬────────────┐
│   Workers  │    Time    │   Speedup    │  Segments  │
├────────────┼────────────┼──────────────┼────────────┤
│     1      │   120.50s  │      1.00x   │       245  │
│     2      │    68.30s  │      1.76x   │       244  │
│     4      │    38.20s  │      3.15x   │       243  │
│     8      │    28.90s  │      4.17x   │       242  │
└────────────┴────────────┴──────────────┴────────────┘

🏆 BEST CONFIGURATION: 8 workers
   Time: 28.90s
   Speedup: 4.17x vs single worker

📈 EFFICIENCY ANALYSIS:
   1 workers: 100.0% efficient (1.00x speedup / 1 workers)
   2 workers: 88.0% efficient (1.76x speedup / 2 workers)
   4 workers: 78.8% efficient (3.15x speedup / 4 workers)
   8 workers: 52.1% efficient (4.17x speedup / 8 workers)
```

---

## 🚀 Como Executar

### Passo 1: Baixar vídeo de teste
```bash
# Baixar vídeo padrão (curto)
python teste_melhoria/download_test_video.py

# OU especificar vídeo customizado (5-10 minutos recomendado)
python teste_melhoria/download_test_video.py "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

### Passo 2: Escolher tipo de teste

**Opção A: Comparação completa (Single vs Multi)**
```bash
python teste_melhoria/benchmark_parallel_transcription.py
```
- Testa ambos os métodos
- Compara qualidade e performance
- Mais demorado (~3-5 minutos)

**Opção B: Teste rápido de múltiplos workers**
```bash
python teste_melhoria/test_multi_workers.py
```
- Testa apenas método paralelo
- Múltiplas configurações de workers
- Mais rápido (~2-4 minutos)

---

## 📊 Interpretando Resultados

### Speedup
- **> 3.0x**: Excelente parallelização, overhead mínimo
- **2.0-3.0x**: Boa parallelização, overhead aceitável
- **1.5-2.0x**: Parallelização moderada, avaliar trade-offs
- **< 1.5x**: Overhead alto, considerar single-core

### Eficiência
```
Eficiência = (Speedup / Num_Workers) × 100%
```
- **> 80%**: Excelente utilização de recursos
- **60-80%**: Boa utilização, overhead razoável
- **40-60%**: Utilização moderada, overhead significativo
- **< 40%**: Má utilização, muito overhead

### Qualidade (Diferença de Segmentos)
- **< 5%**: Qualidade equivalente
- **5-10%**: Pequena variação, aceitável
- **> 10%**: Revisar estratégia de chunks/overlap

---

## ⚙️ Configurações Importantes

### `whisper_parallel_service.py`
```python
WhisperParallelTranscriptionService(
    model_name="base",           # Modelo Whisper: tiny, base, small, medium, large
    device="cpu",                # Dispositivo: cpu ou cuda
    num_workers=4,               # Número de workers paralelos (None = auto)
    chunk_duration_seconds=120   # Duração de cada chunk em segundos
)
```

**Recomendações:**
- **num_workers**: 
  - CPU 4 cores → 4 workers
  - CPU 8 cores → 6-8 workers
  - Evitar > CPU cores (overhead)
  
- **chunk_duration_seconds**:
  - Muito curto (< 60s) → overhead alto
  - Muito longo (> 180s) → parallelismo ruim
  - **Ideal: 90-120s** para balance

---

## 🔬 Overhead Esperado

### Fontes de Overhead
1. **Splitting de áudio**: ~1-2s (FFprobe)
2. **Process spawning**: ~0.5s por worker
3. **Merge de segmentos**: ~0.2-0.5s
4. **Perda de contexto**: chunks independentes
5. **Cleanup**: ~0.1s

### Overhead Total Estimado
- **4 workers**: ~15-20% do tempo total
- **8 workers**: ~20-25% do tempo total
- **16 workers**: ~30-40% do tempo total (não recomendado)

**Exemplo:**
```
Áudio de 10 minutos (600s)
Transcrição teórica por chunk: 30s
4 workers teórico: 600s / 4 = 150s

Overhead (20%): 150s × 0.20 = 30s
Tempo real: 150s + 30s = 180s
Speedup real: 600s / 180s = 3.33x (vs 4x teórico)
```

---

## 📈 Resultados Esperados

### Exemplo: Vídeo de 10 minutos, Modelo Base, CPU 8 cores

| Workers | Tempo (s) | Speedup | Eficiência | Recomendação |
|---------|-----------|---------|------------|--------------|
| 1       | 480.0     | 1.00x   | 100%       | Baseline     |
| 2       | 260.0     | 1.85x   | 92%        | ✅ Excelente |
| 4       | 152.0     | 3.16x   | 79%        | ✅ Ótimo     |
| 8       | 95.0      | 5.05x   | 63%        | ✅ Bom       |
| 16      | 78.0      | 6.15x   | 38%        | ⚠️ Overhead  |

**Conclusão:** 4-8 workers = sweet spot para maioria dos casos

---

## 🐛 Troubleshooting

### Erro: "Test video not found"
```bash
# Baixar vídeo de teste primeiro
python teste_melhoria/download_test_video.py
```

### Erro: "yt-dlp not found"
```bash
pip install yt-dlp
```

### Erro: "FFmpeg not found"
```bash
# Windows (Chocolatey)
choco install ffmpeg

# Linux (APT)
sudo apt-get install ffmpeg

# MacOS (Homebrew)
brew install ffmpeg
```

### Performance pior que esperado
- Verificar CPU cores: `print(os.cpu_count())`
- Reduzir `num_workers` se > CPU cores
- Aumentar `chunk_duration_seconds` se overhead alto
- Verificar se outros processos estão usando CPU

### Qualidade diferente entre métodos
- Normal: < 5% diferença de segmentos
- Se > 10%: considerar aumentar overlap entre chunks (não implementado ainda)

---

## 📝 Próximos Passos

### Se resultados forem positivos (speedup > 2x):
1. ✅ Integrar ao código principal
2. ✅ Adicionar variável de ambiente `ENABLE_PARALLEL_TRANSCRIPTION`
3. ✅ Atualizar CHANGELOG.md
4. ✅ Documentar no README principal
5. ✅ Adicionar testes automatizados

### Se resultados forem negativos (speedup < 1.5x):
1. ✅ Documentar como experimento
2. ✅ Analisar fontes de overhead
3. ✅ Considerar estratégias alternativas:
   - Overlap entre chunks
   - Batch processing de múltiplos áudios
   - GPU acceleration (CUDA)

---

## 📚 Referências

- **ProcessPoolExecutor**: https://docs.python.org/3/library/concurrent.futures.html
- **Whisper Model**: https://github.com/openai/whisper
- **FFmpeg**: https://ffmpeg.org/documentation.html
- **yt-dlp**: https://github.com/yt-dlp/yt-dlp

---

## 🎯 Objetivo

Validar empiricamente se a transcrição paralela por chunks acelera o processamento de áudios individuais em CPUs multi-core, comparando:

- ✅ Tempo de processamento (speedup)
- ✅ Qualidade da transcrição (segmentos)
- ✅ Detecção de idioma (consistência)
- ✅ Eficiência de recursos (CPU utilization)

**Hipótese:** Com 4 cores, esperamos speedup de ~3.2x (80% de 4x teórico), considerando 20% de overhead para splitting, merging e context boundaries.

---

*Última atualização: $(date)*
