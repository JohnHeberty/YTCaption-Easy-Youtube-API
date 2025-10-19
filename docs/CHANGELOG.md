# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [2.0.0] - 2025-10-19

### 🚀 Adicionado

#### **Docker Compose Simplificado**

- **Remoção de Volumes Externos**
  - Container totalmente autossuficiente sem volumes externos
  - Cache de modelos Whisper dentro do container
  - Logs dentro do container (acesso via `docker-compose logs`)
  - Simplificação da configuração Docker

- **Configurações v2.0.0 no Docker Compose**
  - `ENABLE_PARALLEL_TRANSCRIPTION=true` por padrão
  - `PARALLEL_WORKERS=2` configurado
  - `PARALLEL_CHUNK_DURATION=120` otimizado
  - `AUDIO_LIMIT_SINGLE_CORE=300` para seleção inteligente
  - Limites de memória ajustados para 8GB (suporta 2 workers)

#### **Nova Arquitetura de Transcrição Paralela (Persistent Worker Pool)**

- **Persistent Worker Pool** (`persistent_worker_pool.py`)
  - Workers carregam modelo Whisper **UMA VEZ** no startup da aplicação
  - Workers processam chunks via fila `multiprocessing.Queue`
  - Elimina overhead de recarregar modelo a cada chunk (~800MB para modelo `base`)
  - Speedup de **3-5x** comparado à versão anterior
  - Speedup de **7-10x** para vídeos longos (>45min)

- **Session Manager** (`temp_session_manager.py`)
  - Gerenciamento de sessões isoladas por requisição
  - Cada request recebe pasta única: `temp/{session_id}/`
  - Subpastas organizadas: `download/`, `chunks/`, `results/`
  - Cleanup automático após processamento
  - Limpeza de sessões antigas (>24h)
  - Session ID único: `session_{timestamp}_{uuid}_{ip_hash}`

- **Chunk Preparation Service** (`chunk_preparation_service.py`)
  - Pré-criação de chunks em disco via FFmpeg
  - Extração assíncrona paralela de chunks
  - Chunks salvos em `temp/{session_id}/chunks/`
  - Otimização: chunks prontos antes do processamento pelos workers

- **Parallel Transcription Service** (`parallel_transcription_service.py`)
  - Orquestração completa do fluxo de transcrição paralela
  - Integração com worker pool, session manager e chunk preparation
  - Fluxo: session → download → convert → chunks → workers → merge → cleanup
  - Suporte a requisições concorrentes com isolamento de sessão
  - Logs detalhados de timing (convert, chunk prep, processing, total)

- **Lifecycle Management** (`main.py`)
  - Worker pool iniciado no startup da aplicação (FastAPI lifespan)
  - Workers carregam modelo durante inicialização (logs de timing)
  - Shutdown graceful dos workers (aguarda tasks em andamento)
  - Cleanup automático de sessões antigas no startup

- **Intelligent Transcription Factory** (`transcription_factory.py`)
  - Seleção automática de modo baseado em duração do áudio:
    - `< 300s (5min)`: Single-core (mais eficiente para áudios curtos)
    - `>= 300s (5min)`: Paralelo (mais rápido para áudios longos)
  - Fallback automático para single-core em caso de erro
  - Configuração via `AUDIO_LIMIT_SINGLE_CORE`

#### **Documentação**

- **Architecture Guide** (`docs/10-PARALLEL-ARCHITECTURE.md`)
  - Arquitetura técnica completa com diagramas
  - Descrição de componentes e fluxo de execução
  - Estrutura de pastas e sessões
  - Configuração recomendada por hardware
  - Comparações de performance (V1 vs V2)
  - Troubleshooting e debugging

- **Integration Guide** (`docs/11-PARALLEL-INTEGRATION-GUIDE.md`)
  - Guia de implementação e integração
  - Exemplos de uso e testes
  - Métricas de performance esperadas
  - Configurações para diferentes ambientes
  - Procedimentos de teste e validação

- **Updated .env.example**
  - Documentação completa das configurações do worker pool
  - Tabela de consumo de RAM por modelo/worker
  - Valores recomendados para diferentes cenários
  - Explicações detalhadas de cada parâmetro

#### **Configurações**

- `ENABLE_PARALLEL_TRANSCRIPTION` - Ativa/desativa worker pool
- `PARALLEL_WORKERS` - Número de workers persistentes (padrão: 2)
- `PARALLEL_CHUNK_DURATION` - Duração dos chunks em segundos (padrão: 120s)
- `AUDIO_LIMIT_SINGLE_CORE` - Limite para seleção automática de modo (padrão: 300s)

---

### ⚡ Melhorado

- **Performance de Transcrição Paralela**
  - **ANTES:** Vídeo de 45min levava ~22 minutos (V1)
  - **DEPOIS:** Vídeo de 45min leva ~2-3 minutos (V2)
  - **Speedup:** 7-10x para vídeos longos

- **Uso de Memória**
  - Modelo carregado 1x por worker (vs N vezes por request na V1)
  - Redução de ~23x no número de carregamentos para vídeo de 45min
  - Memória previsível: `(workers × tamanho_modelo) + overhead`

- **Concorrência**
  - Suporte a múltiplas requisições simultâneas
  - Isolamento completo entre sessões (sem conflitos de arquivos)
  - Workers compartilhados entre requests (pool único)

- **Logs e Observabilidade**
  - Logs detalhados por sessão (`[PARALLEL] Session {id}`)
  - Timing de cada fase: download, conversão, chunk prep, processamento
  - Logs de startup dos workers com tempo de carregamento do modelo
  - Rastreamento de erros por chunk

---

### 🗑️ Removido (Breaking Changes)

#### **Versão Antiga de Transcrição Paralela (V1 - Descontinuada)**

- ❌ **Arquivo removido:** `parallel_transcription_service.py` (V1)
  - **Motivo:** Performance extremamente ruim (7-10x mais lenta)
  - **Substituído por:** Nova implementação com persistent worker pool
  - **Backup disponível em:** `parallel_transcription_service_v1_deprecated.py`

- ❌ **ProcessPoolExecutor por chunk** - Removido
  - Cada chunk criava novo processo e recarregava modelo
  - Substituído por workers persistentes com fila de tarefas

- ❌ **Fallback para V1** - Removido
  - Factory não tenta mais instanciar versão V1 antiga
  - Em caso de falha no worker pool, usa apenas single-core

---

### 🔧 Corrigido

- **Problema crítico de performance em modo paralelo**
  - Identificado: Modelo Whisper (~800MB) era recarregado a cada chunk
  - Para vídeo de 45min: 23 chunks = 23 carregamentos = overhead massivo
  - Resultado: Modo paralelo 3-4x MAIS LENTO que single-core
  - Solução: Workers persistentes carregam modelo 1x no startup

- **Conflitos de arquivos em requisições concorrentes**
  - Problema: Múltiplos requests salvavam chunks na mesma pasta `/temp`
  - Solução: Session isolation com `temp/{session_id}/` único por request

- **Memory leaks em sessões longas**
  - Problema: Pastas temporárias não eram limpas após erro
  - Solução: Cleanup em `finally` block + limpeza automática de sessões antigas

---

### 📊 Métricas de Performance

#### **Teste Real (Proxmox LXC, 4 cores, modelo base)**

| Método | Vídeo 45min (2731s) | Speedup vs V1 | Speedup vs Single |
|--------|---------------------|---------------|-------------------|
| V1 Paralelo (antiga) | ~22 minutos | 1.0x (baseline) | 0.27x (MAIS LENTO!) |
| Single-core | ~6 minutos | 3.67x | 1.0x (baseline) |
| **Paralelo (nova)** | **~2-3 minutos** | **7-10x** ⚡ | **2-3x** 🚀 |

#### **Consumo de Recursos**

**Configuração Recomendada (Produção):**
```bash
WHISPER_MODEL=base
PARALLEL_WORKERS=2
PARALLEL_CHUNK_DURATION=120
```

- **RAM:** ~2-3GB (2 workers × ~800MB + overhead)
- **CPU:** 2 cores ativos durante processamento
- **Disco:** Temporário (~500MB por sessão, auto cleanup)

---

### 🔄 Migração da V1 para V2

#### **Automática**
Não é necessária nenhuma ação. A nova versão é ativada automaticamente com:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
```

#### **Configuração Recomendada**
```bash
# .env
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2              # Conservador (2-3GB RAM)
PARALLEL_CHUNK_DURATION=120     # 2 minutos por chunk
AUDIO_LIMIT_SINGLE_CORE=300     # Usa paralelo para áudios >5min
```

#### **Rollback (se necessário)**
Em caso de problemas, desative o modo paralelo:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```
O sistema usará single-core (versão estável).

---

### ⚠️ Breaking Changes

1. **Remoção da V1 Paralela**
   - Código antigo de transcrição paralela foi descontinuado
   - Arquivo renomeado para `*_v1_deprecated.py`
   - Não há mais fallback para V1 - apenas para single-core

2. **Novos Requisitos de Sistema**
   - Worker pool requer RAM adicional: `workers × tamanho_modelo`
   - Configuração de `PARALLEL_WORKERS` deve ser ajustada ao hardware disponível

3. **Mudanças de Comportamento**
   - Workers são iniciados no **startup da aplicação** (não por request)
   - Primeira requisição NÃO tem delay de carregamento de modelo
   - Shutdown da aplicação aguarda conclusão de tasks em andamento

---

### 📚 Referências

- **Documentação Técnica:** `docs/10-PARALLEL-ARCHITECTURE.md`
- **Guia de Integração:** `docs/11-PARALLEL-INTEGRATION-GUIDE.md`
- **Configuração:** `.env.example`
- **Issue Report:** Performance issue com modo paralelo (22min vs 6min)

---

### 🙏 Agradecimentos

Especial agradecimento ao feedback do usuário sobre o problema de performance crítico que levou à completa reestruturação da arquitetura paralela.

---

## [1.3.3] - 2025-10-18

### Adicionado
- Documentação SOLID refatorada (9 documentos criados)
- Suporte a CLI options no start.sh
- Melhorias no sistema de logs

### Corrigido
- Correções de lint em diversos arquivos
- Melhorias no script de inicialização

---

## [1.2.0] - 2025-10-15

### Adicionado
- Transcrição paralela inicial (V1 - descontinuada em 2.0.0)
- Suporte a chunks de áudio
- Processamento usando ProcessPoolExecutor

### Conhecido
- Performance ruim em modo paralelo (identificado e resolvido em 2.0.0)

---

[2.0.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v2.0.0
[1.3.3]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v1.3.3
[1.2.0]: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/releases/tag/v1.2.0
