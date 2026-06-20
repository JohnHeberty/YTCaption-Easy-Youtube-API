# Política do Agente

## Qualidade

Sempre:
1. Entender a tarefa antes de agir.
2. Identificar o escopo real da mudança.
3. Planejar tarefas médias ou complexas.
4. Localizar símbolos, arquivos e fluxos antes de abrir arquivos inteiros.
5. Ler somente o necessário.
6. Fazer a menor alteração correta.
7. Validar com comando adequado quando possível.
8. Registrar decisões, progresso e próximos passos no `MEMORY.md`.
9. Explicar limitações e riscos restantes.
10. Responder em português do Brasil, de forma direta e técnica.

## Anti-alucinação

Nunca:
- Inventar arquivo, função, rota, componente, teste ou comando.
- Afirmar que rodou um comando sem ter rodado.
- Afirmar que uma alteração compila sem validação real.
- Assumir backend existente.
- Assumir workspace manager na raiz.
- Assumir que os apps estão linkados entre si.
- Usar documentação externa sem necessidade.
- Usar memória antiga como substituta de inspeção quando o código atual importa.

Quando houver incerteza, declarar:
```
Não consegui validar X.
Assumi Y porque Z.
Risco restante: ...
```

## Segurança

Nunca fazer automaticamente:
- Deploy.
- Reset de git.
- Remoção em massa.
- Migração destrutiva.
- Alteração de infraestrutura.
- Instalação global de dependências.
- Troca ampla de biblioteca.
- Reestruturação global sem pedido explícito.
- Comandos com risco de perda de dados.
- Alteração de arquivos fora do escopo.

Se a tarefa exigir ação potencialmente destrutiva, pedir confirmação explícita.

## Menor Alteração Suficiente

A mudança deve ser a menor que resolva corretamente o problema.

Evitar:
- Refatorar arquivos não relacionados.
- Trocar arquitetura.
- Trocar biblioteca.
- Mover diretórios.
- Renomear componentes.
- Alterar UI fora do escopo.
- Misturar melhorias não solicitadas.

Só ampliar escopo se:
- For necessário para corrigir o problema.
- Houver forte acoplamento entre apps.
- Houver risco claro de regressão.
- O usuário pedir explicitamente.

Se alterar um serviço, verificar se outros serviços afetados precisam de ajustes. Não alterar automaticamente sem necessidade.

## Política de Bugs

Fluxo:
1. Ler `MEMORY.md`.
2. Entender fluxo afetado.
3. Localizar causa.
4. Ler apenas arquivos relevantes.
5. Fazer menor alteração possível.
6. Validar fluxo afetado.
7. Atualizar memória.
8. Responder com resumo objetivo.

Não fazer: refatoração ampla, troca de biblioteca, alteração visual fora do bug, alteração em outro app sem necessidade, backend fictício.

## Política de Features

Fluxo:
1. Ler `MEMORY.md`.
2. Confirmar serviço alvo (`SE1`-`SE11`, ou `shared`).
3. Localizar padrões existentes.
4. Reutilizar componentes e estilos.
5. Implementar menor escopo funcional.
6. Verificar espelhamento entre apps.
7. Validar.
8. Atualizar memória.

Preservar: português do Brasil, tema, responsividade, navegação existente, estrutura atual, base paths, storage keys.

Evitar: dependência nova, duplicação nova sem necessidade, mover arquivos, reescrever fluxo inteiro, criar backend fictício.

## Política de Refatoração

Refatorar somente com objetivo claro.

Boa refatoração: preserva comportamento observável, reduz duplicação real, melhora legibilidade, melhora testabilidade, reduz risco futuro, respeita padrões existentes, é validada.

Proibido sem pedido explícito:
- Trocar navegação/React Router.
- Criar workspace manager.
- Consolidar apps.
- Mover shared code entre apps.
- Trocar Tailwind.
- Alterar theme system.
- Criar backend.
- Substituir storage.
- Alterar base paths.
- Reestruturar monorepo.

## Política de Documentação

Ao criar ou alterar documentação:
- Ser direto.
- Manter português do Brasil.
- Documentar comandos reais.
- Documentar limitações reais.
- Não inventar features.
- Não prometer backend inexistente.
- Não duplicar documentação desnecessária.
- Referenciar arquivos críticos em vez de colar código inteiro.

## Regras de Edição

Antes de editar:
1. Ler `MEMORY.md`.
2. Identificar arquivos relevantes.
3. Explicar plano curto quando fizer sentido.
4. Confirmar escopo mentalmente.
5. Não abrir arquivos inteiros sem necessidade.
6. Não alterar estrutura global sem necessidade.
7. Preservar padrões existentes.

Durante a edição:
- Fazer menor alteração suficiente.
- Preservar estilo existente.
- Evitar renomeações desnecessárias.
- Evitar mover arquivos sem necessidade.
- Não trocar biblioteca sem pedido.
- Não adicionar dependência sem necessidade.
- Não alterar configuração global sem necessidade.
- Não misturar mudanças entre apps sem explicar.
- Manter textos de UI em português do Brasil.
- Manter compatibilidade com navegação atual.
- Manter compatibilidade com paths de deploy.

Depois de editar:
1. Listar arquivos alterados.
2. Explicar o que mudou.
3. Rodar validação quando possível.
4. Informar comandos de validação.
5. Mencionar se não foi possível testar.
6. Atualizar `MEMORY.md`.

## Padrões de Programação

### TypeScript / React
- Preservar tipos existentes.
- Evitar `any` sem justificativa.
- Preferir tipos explícitos em props.
- Manter componentes coesos.
- Evitar lógica complexa inline no JSX.
- Extrair helpers apenas quando simplificar.
- Preservar padrão visual existente.
- Não introduzir estado global novo sem necessidade.
- Não substituir state machine atual sem pedido.

### Python
Quando criar ou alterar Python, escrever código fortemente tipado e testável.

Obrigatório quando aplicável:
```python
from __future__ import annotations
```

Usar: type hints completos, `dataclass`, `TypedDict`, `Protocol`, `Literal`, `Enum`, `pathlib.Path`, exceções específicas, funções pequenas, separação entre I/O e regra de negócio, testes com `pytest`.

Evitar: `Any` sem justificativa, `except Exception` genérico, funções grandes, código executando no import, variáveis globais mutáveis, prints como logging permanente, lógica de negócio acoplada a CLI, parsing frágil sem validação.

Checklist Python:
```
[ ] Assinaturas têm tipos?
[ ] Retornos têm tipos?
[ ] Caminhos usam pathlib?
[ ] Erros são tratados explicitamente?
[ ] Há testes para caminho feliz?
[ ] Há testes para bordas?
[ ] O código é determinístico?
[ ] I/O está separado da regra de negócio?
[ ] Não há Any desnecessário?
[ ] Não há estado global perigoso?
```

Ferramentas Python (quando existirem no projeto ou quando o usuário pedir):
```bash
python -m pytest
python -m mypy .
python -m ruff check .
python -m ruff format .
```

## Critérios de Pronto

Uma tarefa só está pronta quando:
```
[ ] Objetivo do usuário foi atendido.
[ ] Escopo foi respeitado.
[ ] Arquivos relevantes foram localizados.
[ ] Alteração foi mínima e segura.
[ ] Padrões existentes foram preservados.
[ ] Validação foi executada ou limitação foi declarada.
[ ] Riscos restantes foram informados.
[ ] MEMORY.md foi atualizado quando necessário.
[ ] Resposta final lista arquivos alterados e validação.
```

Código só deve ser considerado pronto quando:
```
[ ] Compila ou a limitação foi informada.
[ ] Não introduz dependência desnecessária.
[ ] Não altera comportamento fora do escopo.
[ ] Trata erros relevantes.
[ ] Mantém estilos e padrões do projeto.
[ ] Tem tipos adequados.
[ ] Foi validado no subprojeto correto.
[ ] Casos de borda principais foram considerados.
```

Código Python só deve ser considerado pronto quando:
```
[ ] Usa type hints completos.
[ ] Evita Any sem justificativa.
[ ] Usa pathlib para caminhos.
[ ] Separa I/O de regra de negócio.
[ ] Tem funções pequenas e coesas.
[ ] Tem erros específicos.
[ ] Tem testes pytest quando aplicável.
[ ] Pode ser checado com mypy/pyright quando disponível.
[ ] Pode ser checado com ruff quando disponível.
```
