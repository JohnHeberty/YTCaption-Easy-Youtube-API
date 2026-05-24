# Contexto e Ferramentas

## Política de Contexto

### Regra de Ouro

Antes de ler muito conteúdo:
1. Entenda a pergunta.
2. Classifique a tarefa.
3. Escolha a ferramenta mais econômica.
4. Localize antes de ler.
5. Leia somente o trecho necessário.
6. Resuma antes de continuar.
7. Salve conhecimento durável em memória quando útil.

### Compressão de Contexto

Quando o contexto ficar grande ou após muitas chamadas de ferramenta, resumir o estado atual antes de continuar. Se houver ferramenta de compactação disponível, usá-la.

Objetivo: manter o contexto leve, melhorar velocidade de processamento e evitar buildup.

### Nunca Despejar no Contexto

Nunca despejar: repositório inteiro, arquivos inteiros sem necessidade, outputs completos do Repomix, documentação externa inteira, logs longos, outputs repetidos, builds gerados, arquivos já analisados, arquivos binários, imagens, lockfiles, sourcemaps, minified files.

### Fluxo Padrão

```
1. Localizar.
2. Ler trecho mínimo.
3. Resumir.
4. Editar somente o necessário.
5. Validar.
6. Atualizar memória.
```

Limites práticos:
- Ler no máximo 3 a 5 arquivos por etapa.
- Não abrir arquivo inteiro se busca por símbolo resolver.
- Não usar Repomix no monorepo inteiro sem pedido explícito.
- Não usar Context7 sem biblioteca/API específica.
- Não repetir output de comando já visto.
- Não reler arquivo inteiro se resumo suficiente existir.
- Não executar comandos longos sem necessidade.

## Classificação da Tarefa

Antes de agir, classificar mentalmente a tarefa:
```
A. Bug específico
B. Feature
C. Refatoração
D. Análise de arquitetura
E. Comparação entre apps
F. Dúvida de biblioteca/API
G. Ajuste visual/UI
H. Validação/build/lint
I. Limpeza de contexto
J. Documentação
```

Usar a classificação para escolher ferramentas e profundidade.

## Ordem de Ferramentas

Ordem padrão:
```
1. Busca nativa (glob/grep) — sempre primeiro
2. Ferramentas de code intelligence (se disponíveis)
3. Repomix — apenas para visão ampla
4. Context7 — apenas para documentação externa específica
5. Ferramentas nativas de edição e shell
```

Decisão rápida:
```
Pergunta específica de código → busca por símbolo/arquivo
Bug ou feature → localização → leitura pontual → edição mínima → validação
Arquitetura de uma área → busca específica → Repomix com includes específicos se necessário
Comparação entre apps → busca específica → Repomix com includes específicos
Dúvida de biblioteca/API → Context7
Conhecimento reutilizável → MEMORY.md
Comando de validação → shell no subprojeto correto
```

## Busca por Símbolos e Arquivos

Usar ferramentas de busca para:
- Localizar arquivos.
- Localizar classes, funções, componentes.
- Localizar referências.
- Entender símbolos.
- Navegar entre módulos.
- Entender impacto de alteração.
- Mapear chamadas.

Protocolo de busca:
1. Localizar símbolo, componente, rota ou função.
2. Ler apenas trechos relevantes.
3. Evitar abrir arquivos inteiros.
4. Usar referências para entender impacto.
5. Salvar conhecimento durável em memória se descobrir algo reutilizável.

## Repomix

Usar somente quando a tarefa exigir entender vários arquivos juntos. Não usar para pergunta específica se busca por símbolo resolver.

Usar para: visão geral de módulo, análise arquitetural, comparação entre apps, análise de fluxo que cruza muitos arquivos, revisão ampla antes de refatoração solicitada, entender estrutura de uma área, resumir muitos arquivos.

Configuração: `directory = /workspace`, `compress = true`. Sempre usar includes específicos.

Includes recomendados:
```
PetCare/src/**, PetCare/pages/**, PetCare/components/**, PetCare/shared/**, PetCare/ui/**
PetCarePro/src/**, PetCarePro/pages/**, PetCarePro/components/**, PetCarePro/shared/**, PetCarePro/ui/**
expo/PetCareExpo/src/**, expo/PetCareExpo/components/**, expo/PetCareExpo/screens/**
```

Evitar `**/*` sem pedido explícito de análise global.

Nunca incluir: `node_modules/**`, `vendor/**`, `dist/**`, `build/**`, `.git/**`, `.next/**`, `.nuxt/**`, `coverage/**`, `logs/**`, `*.log`, `*.lock`, `*.min.js`, `*.map`, `*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`, `*.ico`, `*.pdf`, `*.zip`, `*.rar`, `*.7z`.

Protocolo: definir escopo exato antes, usar includes pequenos, usar output como índice/resumo, buscar no output antes de ler grandes blocos, ler somente arquivos ou trechos necessários depois, não colar output completo na resposta, não repetir se o resumo anterior ainda for suficiente.

## Context7

Usar somente quando precisar confirmar API, comportamento ou configuração de biblioteca externa.

Usar para: React, Vite, Expo, React Native, React Navigation, Tailwind, Leaflet, AsyncStorage, bibliotecas npm, APIs/frameworks.

Não usar quando: o problema puder ser resolvido pelo código local, a tarefa for puramente interna, não houver biblioteca/API específica, a documentação não for necessária.

Protocolo: buscar somente a biblioteca necessária, buscar somente o tópico necessário, não trazer documentação inteira, não colar blocos grandes, aplicar a documentação ao código local.

Exemplos bons: "React Navigation stack header options", "Expo AsyncStorage usage", "Vite base path config".
Exemplos ruins: "React docs", "Expo docs", "Vite docs".

## Subagents

Sempre que disponível e adequado, usar subagents para tarefas que possam gerar muito ruído.

Usar para: investigação paralela, análise de impacto, comparação entre apps, revisão de código, busca de padrões, validação de hipóteses, análise de logs grandes, leitura de documentação extensa.

Objetivo: evitar despejo de logs e detalhes desnecessários no contexto principal.

Ao usar subagents: dar escopo estreito, pedir saída resumida, pedir arquivos/símbolos relevantes, pedir riscos e incertezas, não pedir dumps completos.

## Gerenciamento de Contexto Longo

Quando o contexto estiver ficando grande:
1. Resumir decisões importantes.
2. Descartar logs antigos.
3. Descartar outputs repetidos.
4. Manter lista de arquivos alterados.
5. Manter pendências.
6. Manter próximos passos.
7. Atualizar `MEMORY.md`.
8. Continuar somente com resumo útil.

Se uma ferramenta retornar output grande: resumir o essencial, manter nomes de arquivos, manter linhas ou símbolos importantes, descartar o restante, não repetir o output completo.
