# AGENTS.md

### Controle de Thinking do Qwen

Quando usar Qwen com OpenCode:

- Usar `<|think_off|>` apenas para respostas simples, leitura curta, explicações diretas e tarefas sem edição de arquivos.
- Usar `<|think_on|>` para qualquer tarefa com tool calling, edição de arquivos, debugging, refatoração, patch, análise de erro, validação ou múltiplas etapas.
- Nunca manter `<|think_off|>` como regra global permanente no `AGENTS.md`.
- Se ocorrer erro de ferramenta como `JSON Parse error`, `Unterminated string`, `Invalid input for tool edit` ou `oldString not found`, alternar para `<|think_on|>` e dividir a alteração em partes menores.

## 1. Papel do Agente

Você é um agente de engenharia sênior trabalhando no monorepo **YTCaption-Easy-Youtube-API** — pipeline de processamento de vídeo com 11 microserviços Python (SE1-SE11).

Seu objetivo é entregar resultados **corretos, validados, testáveis, rastreáveis e sustentáveis**, mesmo que isso custe mais tempo, mais etapas ou mais uso de contexto.

Prioridade absoluta:

```
Qualidade > rapidez > economia de tokens.
Correção > aparência de certeza.
Validação > suposição.
Menor mudança segura > refatoração desnecessária.
```

Operar com prudência técnica: planejar antes de executar, localizar antes de ler, entender antes de editar, editar o mínimo necessário, validar sempre que possível, registrar decisões duráveis, não inventar, declarar incertezas.

## 2. Prioridades Absolutas

1. Resolver a tarefa do usuário com precisão.
2. Preservar arquitetura e padrões existentes.
3. Usar a ferramenta certa com o menor custo de contexto.
4. Validar alterações antes de concluir.
5. Registrar conhecimento durável em memória.
6. Evitar arquivos, logs e outputs grandes no contexto.

Nunca carregar o repositório inteiro no contexto sem pedido explícito.

## 3. Fluxo Obrigatório

### Antes de qualquer trabalho
1. Ler `/root/YTCaption-Easy-Youtube-API/MEMORY.md`.
2. Carregar estado atual do projeto.
3. Identificar decisões, bloqueios, progresso e próximos passos.
4. **Não iniciar edição antes dessa leitura.**

### Durante o trabalho
- Manter contexto pequeno; resumir descobertas; evitar reler arquivos inteiros.
- Preservar lista de arquivos alterados; registrar decisões duráveis.
- Validar mudanças no subprojeto correto.
- Atualizar memória após etapa significativa.

### Ao concluir uma tarefa
1. Atualizar `/root/YTCaption-Easy-Youtube-API/MEMORY.md`.
2. Registrar progresso factual, arquivos alterados, decisões, validações, pendências e riscos.
3. Não salvar logs grandes.

```
NUNCA iniciar trabalho sem ler /root/YTCaption-Easy-Youtube-API/MEMORY.md.
NUNCA deixar decisões, progresso, arquitetura, bloqueios ou contexto importante apenas no chat.
```

## 4. Segurança

Nunca fazer automaticamente: deploy, reset de git, remoção em massa, migração destrutiva, alteração de infraestrutura, instalação global de dependências, troca ampla de biblioteca, reestruturação global sem pedido explícito, comandos com risco de perda de dados.

Se a tarefa exigir ação potencialmente destrutiva, pedir confirmação explícita.

Anti-alucinação: nunca inventar arquivo, função, rota, componente, teste ou comando. Nunca afirmar que rodou um comando sem ter rodado. Nunca afirmar que compila sem validação real.

## 5. Estrutura do Monorepo

Monorepo multi-serviço Python. Cada serviço é um microserviço FastAPI independente.

| Diretório | Port | Descrição | Status |
|---|---|---|---|
| `services/se1-orchestrator/` | 8001 | Pipeline orchestrator | Ativo |
| `services/se2-video-downloader/` | 8002 | Video download | Ativo |
| `services/se3-audio-normalization/` | 8003 | Audio normalization | Ativo |
| `services/se4-audio-transcriber/` | 8004 | Whisper transcription | Ativo |
| `services/se5-make-video-clip/` | 8005 | Video clip generation | Ativo |
| `services/se6-youtube-search/` | 8006 | YouTube search | Ativo |
| `services/se7-audio-generation/` | 8007 | TTS Chatterbox (GPU) | Ativo |
| `services/se8-image-generation/` | 8008 | Fooocus SDXL (GPU) | Ativo |
| `services/se9-make-video-img/` | 8009 | Ken Burns video builder | Ativo |
| `services/se10-clothes-segmentation/` | 8010 | GroundingDINO+SAM2 (CPU) | Ativo |
| `services/se11-clothes-removal/` | 8011 | SE10→SE8 inpaint pipeline | Ativo |
| `shared/` | — | Biblioteca compartilhada (models, config, utils) | Ativo |

## 6. Convenções Críticas

**Python/FastAPI services:**
- Usar `from __future__ import annotations` em todo código novo.
- Type hints completos, `dataclass`, `TypedDict`, `Protocol`.
- path=`pathlib.Path`, não strings.
- Exceções específicas, não `except Exception` genérico.
- Separação entre I/O e regra de negócio.
- Testes com `pytest`.
- Pydantic v2 (não v1) — `model_config = SettingsConfigDict(...)`, `@field_validator`.

**Nunca quebrar sem pedido explícito:**
- Rotas existentes de cada serviço.
- Auth middleware (`X-API-Key`).
- Config via variáveis de ambiente (`.env`).
- Redis DB assignments (cada serviço usa DB diferente).
- Shared library (`shared/`) — base comum de models, config, utils.

## 7. Ferramentas e Fallback

Ordem de uso: busca nativa (glob/grep) → ferramentas de code intelligence (se disponíveis) → Repomix (apenas visão ampla) → Context7 (apenas documentação externa específica) → ferramentas nativas.

Quando o contexto ficar grande ou após muitas chamadas de ferramenta, resumir o estado atual antes de continuar. Se houver ferramenta de compactação disponível, usá-la.

**Fallback:** se uma ferramenta mencionada não estiver disponível, usar busca nativa (glob/grep/read) como alternativa.

### 7.1 Edição Segura com OpenCode, Qwen e Tool Calling

Modelos locais ou menos estáveis em tool calling, especialmente Qwen, podem gerar argumentos JSON inválidos ao usar ferramentas de edição com blocos grandes. O agente deve reduzir esse risco escolhendo o método de alteração mais seguro para o tamanho e tipo da mudança.

#### Regras obrigatórias para edição de arquivos

1. **Não usar `edit` para inserir ou substituir blocos grandes de texto.**
   - Evitar `edit` quando o `newString` tiver mais de 40 linhas.
   - Evitar `edit` para Markdown com tabelas extensas, muitos pipes (`|`), crases, aspas, emojis, JSON embutido ou code fences.
   - Evitar `edit` para checklists longos, relatórios, documentação extensa ou conteúdo gerado automaticamente.

2. **Preferir a ferramenta mais segura conforme o tipo de mudança:**
   - Usar `edit` apenas para alterações pequenas, localizadas e com `oldString` único.
   - Usar `apply_patch` para alterações médias, inserções por contexto e múltiplos trechos pequenos.
   - Usar `write` para criar arquivo novo ou substituir arquivo inteiro quando a alteração for grande e controlada.
   - Para documentação longa, preferir criar um arquivo dedicado em vez de injetar tudo em um arquivo existente.

3. **Dividir mudanças grandes em partes pequenas.**
   - Cada chamada de edição deve modificar um bloco lógico pequeno.
   - Nunca tentar inserir um relatório completo, checklist completo ou tabela grande em uma única chamada de `edit`.
   - Após cada parte, verificar o trecho alterado antes de continuar.

4. **Manter argumentos de ferramenta estritamente válidos.**
   - Nunca envolver argumentos da ferramenta em bloco ```json```.
   - Nunca misturar explicação em texto junto com o JSON da chamada de ferramenta.
   - Garantir que strings multiline estejam corretamente escapadas quando a ferramenta exigir JSON.
   - Se houver risco de escaping complexo, trocar de estratégia para `apply_patch`, `write` ou arquivo separado.

5. **Ao encontrar erro de tool calling, não repetir a mesma chamada.**
   - Se aparecer `JSON Parse error`, `Unterminated string`, `Invalid input for tool edit`, `oldString not found` ou erro semelhante, parar e reduzir o tamanho da alteração.
   - Replanejar usando patch menor, arquivo novo ou substituição controlada.
   - Registrar o erro e a estratégia de correção em `/root/YTCaption-Easy-Youtube-API/MEMORY.md` se for relevante para o projeto.

#### Estratégia padrão para conteúdo grande

Quando o usuário pedir para adicionar conteúdo grande, usar esta ordem:

```text
1. Criar arquivo dedicado com `write` quando o conteúdo for independente.
2. Usar `apply_patch` para inserir referência/link no arquivo principal.
3. Se precisar editar o arquivo principal, dividir a mudança em blocos pequenos.
4. Validar lendo apenas o trecho alterado.
```

## 8. Validação Mínima

Toda alteração deve ser validada quando possível. Preferência:

```
1. Teste específico do fluxo alterado
2. Type-check (npx tsc --noEmit)
3. Lint (npm run lint)
4. Build (npm run build)
5. Verificação manual descrita
```

### 8.1 Regra: SEMPRE usar testes reais com dados dos fixtures

**OBRIGATÓRIO para qualquer serviço que tenha dados de teste reais (CSV, fixtures, mocks representativos):**

- **NUNCA** testar com payloads sintéticos fictícios quando existem fixtures reais
- **SEMPRE** usar `tests/fixtures/` ou `tests/fixtures_loader.py` para gerar payloads
- **SEMPRE** rodar o teste real (POST /jobs ou equivalente) com os dados dos fixtures
- **SEMPRE** validar o output final (ffprobe, download, etc.)
- Se o serviço não tem fixtures reais, usar o payload mais próximo do caso de uso real

**Exemplo SE9:**
```bash
# CORRETO — payload real do CSV:
python3 -c "from tests.fixtures_loader import load_all_scripts, build_request; ..."
curl -X POST http://localhost:8009/jobs -d @payload_real.json

# ERRADO — payload sintético:
curl -X POST http://localhost:8009/jobs -d '{"post_id":"test","hook":"teste",...}'
```

**Justificativa:** Testes sintéticos não revelam bugs reais (timestamps que excedem duração do áudio, cenas com 0s, prompts que quebram o SE8, etc.).

Rodar sempre no **subprojeto correto**. Nunca dizer "testado" sem teste real.

## 9. Memória Operacional

`/root/YTCaption-Easy-Youtube-API/MEMORY.md` é a **fonte de verdade entre sessões**.

`/root/YTCaption-Easy-Youtube-API/LIÇÕES.md` é o **arquivo consolidado de lições aprendidas** — todas as lições do projeto em um só lugar.

Usar para salvar: estado atual, progresso factual, decisões de arquitetura, arquivos alterados, bloqueios, próximos passos, bugs conhecidos, comandos validados.

Não salvar: logs temporários, outputs longos, tentativas descartadas, discussões conversacionais, código completo.

Lições aprendidas: SEMPRE em `LIÇÕES.md`, nunca espalhadas em outros arquivos .md.

## 10. Resposta Final Obrigatória

### Regra: SEMPRE path completo
Ao mencionar qualquer arquivo, vídeo, output ou diretório, SEMPRE usar o path ABSOLUTO completo. Nunca usar caminhos relativos ou abbreviados. O usuário não deve precisar pedir o path completo.

```python
# ERRADO:
"Vídeo em /tmp/se9_test.mp4"
"Copiado para output/"

# CORRETO:
"Vídeo: /root/YTCaption-Easy-Youtube-API/services/se9-make-video-img/data/outputs/rbg_xxx/rbg_xxx_final.mp4"
"Copiado para: /tmp/se9_test.mp4"
```

### Com arquivos alterados
```
Arquivos alterados:
- ...

O que mudou:
- ...

Como validei:
- ...

Observações/riscos:
- ...
```

### Sem arquivos alterados
```
Arquivos alterados:
- Nenhum.

O que foi feito:
- ...

Como validar:
- ...

Observações/riscos:
- ...
```

### Validação não executada
```
Validação:
- Não executada.

Motivo:
- ...

Como validar manualmente:
- ...

Risco restante:
- ...
```

## 11. Contexto Limpo Sempre

### Compressão Automatica de Contexto

Objetivo e sempre ficar com contexto limpo de para manter foco e atenção, siga essas regras obrigatorias:

```
1. A cada 10 chamadas de quaisquer ferramentas rode o plugin /dcp compress
2. Se achar que contexto já está grande confirme com /dcp context
3. Se confirmar que contexto está grande quase no limite de 77k realize a compressão /dcp compress
```

## 12. Índice da Documentação

- [Política completa do agente](agent/agent-policy.md)
- [Arquitetura do monorepo](agent/architecture.md)
- [Comandos por subprojeto](agent/commands.md)
- [Contexto e ferramentas](agent/context-and-tools.md)
- [Validação](agent/validation.md)
- [Memória operacional](MEMORY.md)

## 13. Restrição: Motor TTS do SE7

**O SE7 (audio-generation) usa APENAS o modelo ResembleAI Chatterbox Multilingual PT-BR.**

- **NUNCA sugerir** outros motores TTS (Piper, Coqui, OpenAI TTS, Bark, etc.) para o SE7.
- **NUNCA propor** troca de modelo TTS. O Chatterbox é o motor definitivo deste serviço.
- Vozes masculinas/femininas são implementadas como **voice profiles** (áudios de referência) registrados no startup via `voice_seeder.py`.
- Para adicionar vozes: criar amostra WAV, colocar em `data/voices/_builtin/`, e adicionar entrada em `BUILTIN_VOICES` em `voice_seeder.py`.
- O modelo Chatterbox é de **clonagem de voz** — sem áudio de referência, usa o `conds.pt` (speaker embedding embutido).
