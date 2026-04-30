# Documentacao - Audio Transcriber

Este diretorio concentra o uso da API, contratos de tipos e guias operacionais do servico.

## Arquivos principais
- API_REFERENCE.md: referencia completa dos endpoints atuais.
- TIPOS.md: contratos de request/response e modelos base.
- ERROS.md: padrao de erros HTTP e exemplos de tratamento.
- EXEMPLOS.md: exemplos praticos com curl.
- QUICKSTART.md: bootstrap rapido local.
- GUIA_DE_USO.md: guia de operacao do servico.
- WHISPER_ENGINES.md: comparativo de engines de transcricao.
- RESILIENCE.md: estrategias de resiliencia.

## Ordem recomendada para integracao
1. Ler API_REFERENCE.md para entender os endpoints.
2. Ler TIPOS.md para validar contratos e campos.
3. Implementar tratamento de falhas com ERROS.md.
4. Validar chamadas com EXEMPLOS.md.

## Observacoes
- O contrato foi mantido sem breaking change para clientes existentes.
- Campos adicionais podem existir nas respostas (compatibilidade evolutiva).
- Em caso de job travado, usar /jobs/orphaned e /jobs/orphaned/cleanup.
