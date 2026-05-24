# Documentation Architecture

`docs/` e a casa oficial da documentacao do repositório.

## Principios

1. Organizar por intencao de uso, nao por ordem de execucao ou sprint.
2. Separar documentacao viva de historico e relatorios.
3. Manter uma pagina canonica por servico em `docs/services/`.
4. Usar indices (`README.md`) nas areas com subestrutura.
5. Evitar duplicacao entre a raiz do repo, `docs/` e `services/*/docs/`.

## Taxonomy

- `docs/reference/`: arquitetura geral, estrutura do projeto, contratos compartilhados e regras de organizacao.
- `docs/operations/`: desenvolvimento, comandos, portas, deploy, troubleshooting e operacao local.
- `docs/architecture/adr/`: decisoes arquiteturais registradas.
- `docs/services/`: documentacao canonica do orchestrator e dos microservicos.
- `docs/history/`: relatorios, validacoes, migracoes e marcos historicos.

## Fonte canonica

A referencia global e navegacao devem viver em `docs/`.

Os arquivos `README.md` dentro de `services/*/` e `orchestrator/` podem continuar existindo como pontos de entrada locais, mas devem apontar para a documentacao canonica em `docs/services/` quando houver duplicacao.

## Criterios de classificacao

### Reference

Coloque aqui documentos que respondem:
- como o sistema e estruturado
- quais padroes precisamos manter
- como as partes se relacionam

### Operations

Coloque aqui documentos que respondem:
- como subir, operar, diagnosticar e manter o ambiente
- quais comandos usar
- como configurar o fluxo local e CI

### Services

Coloque aqui documentos que respondem:
- qual o papel do servico
- quais rotas e fluxos principais existem
- como integrar ou operar esse servico

### History

Coloque aqui documentos que respondem:
- o que foi entregue
- o que foi validado
- o que mudou em uma migracao ou iniciativa fechada

## Regras de manutencao

- Todo novo documento deve nascer ja classificado dentro da taxonomy.
- Relatorios temporais nao devem competir com guias permanentes.
- Arquivos com nomes longos e contextuais devem ser reduzidos ou arquivados.
- Preferir `kebab-case` para novos arquivos da arquitetura documental.
