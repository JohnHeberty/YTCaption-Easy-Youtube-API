# AGENTS

## Regras de uso de contexto

Antes de analisar muitos arquivos, use o MCP `repomix`.

O projeto está montado no Docker em:

```text
/workspace
```

Para análise de projeto:

* Use `repomix` com `pack_codebase`.
* Use `directory = /workspace`.
* Use `compress = true`.
* Inclua somente diretórios relevantes.
* Não leia arquivos brutos se o Repomix puder entregar versão compactada.
* Use busca/grep no output do Repomix antes de ler grandes blocos.
* Leia somente trechos necessários.

Quando a pergunta for específica:

* Não compacte o projeto inteiro primeiro.
* Use busca por nome de arquivo, classe, função, rota, componente, tabela ou termo.
* Use Serena para localizar símbolos quando possível.
* Só depois leia o arquivo ou trecho necessário.

Evite ler ou incluir no contexto:

* `node_modules`
* `vendor`
* `dist`
* `build`
* `.git`
* `.next`
* `.nuxt`
* `coverage`
* `logs`
* arquivos `.log`
* arquivos `.lock`
* arquivos `.min.js`
* arquivos `.map`
* imagens
* binários
* arquivos compactados
* outputs gerados

---

## Ordem correta de uso das ferramentas

### 1. Serena

Use Serena primeiro quando a tarefa envolver código específico.

Use Serena para:

* localizar classes
* localizar funções
* localizar componentes
* localizar referências
* entender símbolos
* navegar no código sem ler arquivos inteiros

Preferir Serena para perguntas como:

* "onde está a tela X?"
* "onde essa função é usada?"
* "qual componente controla isso?"
* "qual arquivo altera esse comportamento?"
* "como esse fluxo funciona?"

Não leia o arquivo inteiro se Serena conseguir encontrar o símbolo ou trecho relevante.

### 2. Repomix

Use Repomix quando precisar entender muitos arquivos juntos.

Use Repomix para:

* resumir estrutura do projeto
* analisar vários arquivos
* compactar código removendo comentários e espaços
* gerar visão global
* comparar módulos
* analisar arquitetura

Configuração esperada:

* `directory = /workspace`
* `compress = true`

Sempre preferir includes específicos.

Exemplos de includes:

```text
PetCare/src/**
PetCarePro/src/**
expo/PetCareExpo/src/**
PetCare/components/**
PetCarePro/components/**
PetCare/pages/**
PetCarePro/pages/**
```

Evite includes genéricos como:

```text
**/*
```

a menos que o usuário peça análise global do monorepo.

### 3. Context7

Use Context7 quando precisar de documentação externa.

Use Context7 para:

* React
* Vite
* Expo
* React Native
* React Navigation
* Tailwind
* Leaflet
* AsyncStorage
* bibliotecas npm
* APIs ou frameworks

Não cole documentação inteira no contexto.
Busque somente o trecho necessário.

### 4. DCP

Use DCP quando a conversa começar a ficar grande.

Quando houver muitos comandos, logs ou tentativas antigas:

* compactar histórico
* remover outputs antigos
* preservar decisões importantes
* preservar arquivos alterados
* preservar pendências

O objetivo é evitar compactação automática prematura e perda de contexto útil.

---
