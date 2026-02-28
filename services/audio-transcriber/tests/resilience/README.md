# 🛡️ Testes de Resiliência - Audio Transcriber

Suite completa de testes de resiliência **SEM MOCKS** para validar comportamento em produção.

## 📁 Estrutura

```
tests/resilience/
├── __init__.py                       # Módulo de testes de resiliência
├── conftest.py                       # Fixtures específicas
├── test_transcription_real.py        # ✅ Transcrição real completa
├── test_circuit_breaker.py           # ✅ Comportamento do circuit breaker
├── test_corrupted_files.py           # ✅ Handling de arquivos inválidos
└── README.md                         # Este arquivo
```

## 🎯 Objetivos

Estes testes validam:

1. **Transcrição Real** - Pipeline completo sem mocks
2. **Circuit Breaker** - Proteção contra falhas em cascata
3. **Error Handling** - Arquivos corrompidos, vazios, inválidos
4. **Recuperação** - Sistema se recupera após falhas
5. **Resource Management** - Cleanup de memória/GPU

## ✅ Características

- ❌ **SEM MOCKS** - Usa componentes reais
- ✅ **Arquivo Real** - TEST-.ogg (75KB) para validação
- ✅ **Circuit Breaker** - Testa padrão de resiliência
- ✅ **Error Scenarios** - Arquivos corrompidos, timeouts, etc

## 🚀 Executando os Testes

### Todos os Testes de Resiliência

```bash
cd /root/YTCaption-Easy-Youtube-API/services/audio-transcriber
pytest tests/resilience/ -v -s
```

### Por Categoria

**Transcrição Real**:
```bash
pytest tests/resilience/test_transcription_real.py -v -s
```

**Circuit Breaker**:
```bash
pytest tests/resilience/test_circuit_breaker.py -v -s
```

**Arquivos Corrompidos**:
```bash
pytest tests/resilience/test_corrupted_files.py -v -s
```

### Com Marcadores Específicos

```bash
# Apenas testes reais (carregam modelo real)
pytest tests/resilience/ -m real -v -s

# Apenas testes de circuit breaker
pytest tests/resilience/ -m circuit_breaker -v -s

# Apenas testes de error handling
pytest tests/resilience/ -m error_handling -v -s
```

### Com Cobertura

```bash
pytest tests/resilience/ -v -s --cov=app --cov-report=html
# Relatório: htmlcov/index.html
```

## 📊 Testes Implementados

### 1. `test_transcription_real.py` (4 testes)

| Teste | Descrição | Validação |
|-------|-----------|-----------|
| `test_audio_file_exists_and_valid` | Valida arquivo TEST-.ogg | Formato OGG, tamanho > 10KB |
| `test_model_loading_without_mocks` | Carrega Faster-Whisper real | Sem patches, device detection |
| `test_full_transcription_real_audio` | **Transcrição completa** | Text, segments, words, timestamps |
| `test_circuit_breaker_records_success` | CB registra sucessos | Estado CLOSED, 0 falhas |

**Tempo estimado**: 30-60s (primeira execução: download de modelo)

---

### 2. `test_circuit_breaker.py` (7 testes)

| Teste | Descrição | Validação |
|-------|-----------|-----------|
| `test_circuit_breaker_initialization` | Inicialização | Atributos corretos |
| `test_circuit_starts_closed` | Estado inicial | CLOSED |
| `test_circuit_opens_after_failures` | Abertura após falhas | OPEN após threshold |
| `test_circuit_blocks_calls_when_open` | Bloqueio | CircuitBreakerException |
| `test_circuit_transitions_to_half_open` | Transição após timeout | HALF_OPEN |
| `test_circuit_closes_on_success_from_half_open` | Recuperação | CLOSED após sucesso |
| `test_circuit_breaker_with_real_model_loading` | Integração real | CB funciona com modelo |

**Tempo estimado**: 10-20s

---

### 3. `test_corrupted_files.py` (5 testes)

| Teste | Descrição | Validação |
|-------|-----------|-----------|
| `test_corrupted_file_raises_appropriate_exception` | Arquivo corrompido | Exceção apropriada |
| `test_empty_file_handling` | Arquivo vazio | Não trava |
| `test_non_audio_file_handling` | Arquivo não-áudio | Rejeitado |
| `test_circuit_breaker_tracks_corrupted_file_failures` | CB registra falhas | Protege contra falhas |
| `test_system_recovers_after_corrupted_file` | Recuperação | Funciona após erro |

**Tempo estimado**: 15-30s

---

## 🔍 Exemplo de Saída

```
==================== TESTE REAL: Transcrição Completa (SEM MOCKS) ====================
   Arquivo: TEST-.ogg
   Tamanho: 74.6 KB

   Carregando modelo Faster-Whisper...
   ✓ Modelo carregado no CPU

   Transcrevendo áudio...

============================== VALIDANDO RESULTADO ===============================
   ✓ Estrutura básica válida
   ✓ Success = True
   ✓ Texto transcrito: 1247 caracteres
   ✓ Segments: 15 encontrados
   ✓ Word-level timestamps: 234 palavras
   ✓ Idioma detectado: pt
   ✓ Duração do áudio: 23.50s

==================== ✅ TRANSCRIÇÃO REAL COMPLETA COM SUCESSO ====================
   Tempo de transcrição: 12.34s
   Segments gerados: 15
   Total de palavras: 234
   Comprimento do texto: 1247 chars
   Idioma: pt
   Duração áudio: 23.50s

   📝 Prévia do texto transcrito:
   "Olá, este é um teste de transcrição de áudio usando o modelo..."
==================================================================================
```

## 🐛 Debugging

### Logs Detalhados

```bash
pytest tests/resilience/ -v -s --log-cli-level=DEBUG
```

### Apenas Um Teste

```bash
pytest tests/resilience/test_transcription_real.py::TestRealTranscription::test_full_transcription_real_audio -v -s
```

### Parar no Primeiro Erro

```bash
pytest tests/resilience/ -v -s -x
```

### Ver Traceback Completo

```bash
pytest tests/resilience/ -v -s --tb=long
```

## 📋 Requisitos

- **Python 3.8+**
- **FFmpeg** (para processar áudio)
- **Arquivo TEST-.ogg** em `/tests/TEST-.ogg`
- **~300MB disco** (para modelo Faster-Whisper small)
- **2GB RAM** mínimo para CPU inference

## ⚙️ Configuração

### Variáveis de Ambiente (Opcional)

```bash
# Modelo menor/maior
export WHISPER_MODEL=tiny  # tiny, base, small, medium, large

# Device
export WHISPER_DEVICE=cuda  # cuda ou cpu

# Diretório de modelos
export WHISPER_DOWNLOAD_ROOT=./models
```

## 🎯 Critérios de Sucesso

Todos os testes devem:

- ✅ Passar sem erros
- ✅ Não usar mocks (exceto para fixtures de erro)
- ✅ Validar comportamento real de produção
- ✅ Circuit breaker funcionando
- ✅ Error handling apropriado
- ✅ Recuperação após falhas

## 📈 Cobertura Esperada

| Componente | Cobertura Alvo |
|------------|----------------|
| faster_whisper_manager.py | 85%+ |
| circuit_breaker.py | 90%+ |
| Error handling | 100% dos paths |

## 🔄 Integração com CI/CD

```yaml
# Exemplo GitHub Actions
- name: Run Resilience Tests
  run: |
    cd services/audio-transcriber
    pytest tests/resilience/ -v --cov=app --cov-report=xml
```

## 🐞 Troubleshooting

### Erro: "Modelo não encontrado"

```bash
# Baixa modelo manualmente
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"
```

### Erro: "TEST-.ogg não encontrado"

```bash
# Verifica arquivo
ls -lh tests/TEST-.ogg

# Se não existir, cria um teste sintético
cd tests/
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -ar 16000 TEST-.ogg
```

### Erro: "CUDA out of memory"

```bash
# Força CPU
export WHISPER_DEVICE=cpu
pytest tests/resilience/ -v -s
```

### Testes Lentos

```bash
# Usa modelo menor
export WHISPER_MODEL=tiny
pytest tests/resilience/ -v -s
```

## 📚 Referências

- [Circuit Breaker Pattern](../../docs/RESILIENCE.md)
- [Whisper Engines](../../docs/WHISPER_ENGINES.md)
- [API Reference](../../docs/API_REFERENCE.md)
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)

## 🤝 Contribuindo

Ao adicionar novos testes de resiliência:

1. ❌ **NÃO use mocks** (exceto para simular falhas)
2. ✅ Use arquivo TEST-.ogg para validação
3. ✅ Documente cenário testado
4. ✅ Valide circuit breaker quando relevante
5. ✅ Teste recuperação após falhas
6. ✅ Adicione marcadores apropriados (`@pytest.mark.real`, etc)

## 📝 Checklist de PR

- [ ] Todos os testes passam localmente
- [ ] Novos testes **NÃO** usam mocks
- [ ] Documentação atualizada
- [ ] Cobertura mantida/aumentada
- [ ] Circuit breaker validado

---

**Última atualização**: 2026-02-28  
**Maintainer**: Audio Transcriber Team
