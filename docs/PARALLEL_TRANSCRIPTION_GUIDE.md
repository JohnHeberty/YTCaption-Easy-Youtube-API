# Guia de Configuração - Transcrição Paralela

## 🚀 Visão Geral

A transcrição paralela divide o áudio em chunks e processa em paralelo usando múltiplos workers. Isso pode acelerar a transcrição em **3-4x** em sistemas com múltiplos cores.

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# Habilitar/desabilitar modo paralelo
ENABLE_PARALLEL_TRANSCRIPTION=true

# Número de workers (0 = auto-detect baseado em CPU cores)
PARALLEL_WORKERS=0

# Duração de cada chunk em segundos
PARALLEL_CHUNK_DURATION=120
```

### Requisitos de Hardware

#### CPU
- **Mínimo**: 4 cores físicos
- **Recomendado**: 8+ cores físicos
- **Ideal**: 16+ cores físicos

#### Memória RAM

Cada worker carrega o modelo Whisper na memória:

| Modelo Whisper | RAM por Worker | RAM Total (4 workers) | RAM Total (8 workers) |
|----------------|----------------|-----------------------|-----------------------|
| tiny           | ~400 MB        | ~1.6 GB               | ~3.2 GB               |
| base           | ~800 MB        | ~3.2 GB               | ~6.4 GB               |
| small          | ~1.5 GB        | ~6 GB                 | ~12 GB                |
| medium         | ~3 GB          | ~12 GB                | ~24 GB                |
| large          | ~6 GB          | ~24 GB                | ~48 GB                |

**Fórmula**: `RAM_Total = (RAM_por_Worker × PARALLEL_WORKERS) + 2GB overhead`

## 🛠️ Recomendações por Cenário

### Servidor de Produção (Proxmox/Linux)

**Configuração Agressiva** (máximo desempenho):
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=0  # Auto-detect (usa todos os cores)
PARALLEL_CHUNK_DURATION=120
WHISPER_MODEL=base
```

**Configuração Conservadora** (baixa memória):
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2  # Apenas 2 workers
PARALLEL_CHUNK_DURATION=180  # Chunks maiores
WHISPER_MODEL=tiny
```

### Máquina de Desenvolvimento

**Recomendado**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
WHISPER_MODEL=tiny
```

### Servidor com RAM Limitada

**Exemplo**: 8GB RAM total

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
WHISPER_MODEL=tiny  # ~400MB por worker = 800MB total
```

## 🔧 Troubleshooting

### Erro: "Process pool terminated abruptly"

**Causa**: Falta de memória RAM

**Soluções**:

1. **Reduzir workers**:
```bash
PARALLEL_WORKERS=2  # Ao invés de 4+
```

2. **Usar modelo menor**:
```bash
WHISPER_MODEL=tiny  # Ao invés de base/small
```

3. **Desabilitar paralelo**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

4. **Aumentar RAM do servidor**

### Erro: Timeout

**Causa**: Áudio muito longo ou CPU muito lento

**Soluções**:

1. **Aumentar duração dos chunks**:
```bash
PARALLEL_CHUNK_DURATION=300  # 5 minutos
```

2. **Reduzir workers** (menos sobrecarga):
```bash
PARALLEL_WORKERS=2
```

### Performance Pior que Esperado

**Possíveis causas**:

1. **Poucos cores**: Paralelo tem overhead, só vale a pena com 4+ cores
2. **Áudio curto**: Para áudios <5 minutos, modo normal pode ser mais rápido
3. **Disco lento**: Chunks são salvos/lidos do disco
4. **CPU compartilhada**: Em VMs com CPU compartilhada, paralelo pode competir por recursos

**Solução**: Testar com `ENABLE_PARALLEL_TRANSCRIPTION=false` e comparar tempos

## 📊 Benchmarks Esperados

### Áudio de 30 minutos, Modelo `base`, CPU 8 cores

| Modo     | Tempo    | Speedup |
|----------|----------|---------|
| Normal   | ~10 min  | 1x      |
| Paralelo | ~3 min   | 3.3x    |

### Áudio de 5 minutos, Modelo `base`, CPU 8 cores

| Modo     | Tempo     | Speedup |
|----------|-----------|---------|
| Normal   | ~1.5 min  | 1x      |
| Paralelo | ~1.2 min  | 1.25x   |

**Conclusão**: Speedup aumenta com duração do áudio. Para áudios curtos (<5 min), o overhead do paralelo reduz o ganho.

## 🎯 Recomendações Finais

### Quando Usar Paralelo

✅ Áudios longos (30+ minutos)
✅ Servidor com 8+ cores
✅ RAM suficiente (veja tabela acima)
✅ Produção com alta demanda

### Quando NÃO Usar Paralelo

❌ Áudios curtos (<5 minutos)
❌ CPU com <4 cores
❌ RAM limitada (<4GB disponível)
❌ Desenvolvimento local
❌ VM com CPU compartilhada

## 🔄 Fallback Automático

O sistema detecta automaticamente falhas no modo paralelo e faz fallback para modo normal:

1. Tenta transcrição paralela
2. Se falhar com erro de "process pool", desabilita paralelo
3. Retenta com transcrição normal
4. Mantém paralelo desabilitado para próximas requisições na mesma sessão

Isso garante **alta disponibilidade** mesmo em cenários de falta de recursos.

## 📝 Monitoramento

Verifique logs para entender performance:

```bash
# Ver logs em tempo real
docker-compose logs -f

# Procurar por modo paralelo
docker-compose logs | grep PARALLEL

# Procurar por fallbacks
docker-compose logs | grep "falling back"
```

---

**Dica**: Comece com configuração conservadora e aumente gradualmente baseado nos resultados e recursos disponíveis!
