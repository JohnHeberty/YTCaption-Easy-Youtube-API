# Estrutura do Projeto

**YTCaption-Easy-Youtube-API**  
**Última atualização**: 2026-04-30

---

## Objetivo

Este documento descreve a organizacao atual do repositório e como navegar entre codigo, documentacao, scripts e artefatos operacionais.

Ele complementa a arquitetura documental definida em `docs/reference/documentation-architecture.md` e deve refletir o estado real do repositório, nao um modelo idealizado ou historico.

---

## Estrutura raiz do repositório

```
YTCaption-Easy-Youtube-API/
├── common/                      # Biblioteca compartilhada entre servicos
├── data/                        # Dados temporarios, logs e transcricoes locais
├── docs/                        # Navegacao oficial da documentacao
│   ├── reference/               # Estrutura, arquitetura documental, referencias
│   ├── operations/              # Operacao, desenvolvimento, comandos
│   ├── services/                # Entrada canonica por servico
│   ├── architecture/            # Trilhas arquiteturais e ADR index
│   ├── history/                 # Relatorios e iniciativas concluidas
│   ├── orchestrator/            # Documentacao canonica do orchestrator
│   └── README.md                # Hub principal da documentacao
├── orchestrator/                # Servico coordenador do pipeline
├── scripts/                     # Scripts operacionais e utilitarios
├── services/                    # Microservicos de dominio
│   ├── audio-normalization/
│   ├── audio-transcriber/
│   ├── make-video/
│   ├── video-downloader/
│   └── youtube-search/
├── tests/                       # Artefatos de teste no nivel do repositorio
├── Makefile
├── docker-compose.yml
└── pyproject.toml
```

---

## Arquitetura documental

`docs/` e a fonte oficial de navegacao da documentacao.

### Trilha por intencao

- `docs/reference/`: material estavel para entender estrutura e regras do repositório
- `docs/operations/`: guias para subir, operar, validar e manter o ambiente
- `docs/services/`: porta de entrada canonica para documentacao de servico
- `docs/architecture/`: indices arquiteturais e ADRs
- `docs/history/`: relatorios de iniciativas concluidas e registros historicos

### Regra pratica

- Documentacao viva deve ser descoberta por `docs/`
- Documentacao local em `services/*/docs/` pode continuar existindo
- Quando houver duplicacao, `docs/` define a navegacao oficial e a classificacao correta

---

## Estrutura padrao de microservico

Cada servico tende a seguir esta base, com pequenas variacoes conforme maturidade e necessidades tecnicas:

```
services/{service-name}/
├── README.md                    # Entrada local do servico
├── run.py                       # Entry point principal
├── app/                         # Codigo da aplicacao
├── tests/                       # Testes do servico
├── docs/                        # Documentacao local detalhada
├── scripts/                     # Scripts e utilitarios do servico
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

---

## Regras de organizacao

### Raiz do repositório

- Deve manter `README.md` como documento humano principal.
- `AGENTS.md` pode permanecer como excecao tecnica de tooling.
- Documentacao navegavel e classificavel deve preferencialmente viver em `docs/`.
- Scripts operacionais devem ir para `scripts/` sempre que fizer sentido.

### Raiz de cada servico

- `README.md` pode existir como entrada local.
- `run.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml` e `Makefile` costumam permanecer na raiz do servico.
- Documentos adicionais devem preferir `services/*/docs/`.

### Documentacao

- Documentacao global: `docs/`
- Documentacao local e aprofundada por servico: `services/*/docs/`
- Relatorios de iniciativas concluidas: `docs/history/`
- Entradas canonicas por servico: `docs/services/`

---

## Mapeamento de reorganizacao documental

### Reclassificacoes recentes

| Origem (antes) | Destino (depois) | Tipo |
|----------------|------------------|------|
| `CHECK.md` | `docs/history/CHECK.md` | Documentação histórica |
| `VALIDATION.md` | `docs/history/VALIDATION.md` | Documentação histórica |
| `IMPLEMENTATION_COMPLETE.md` | `docs/history/IMPLEMENTATION_COMPLETE.md` | Documentação histórica |
| `EXECUTIVE_SUMMARY.md` | `docs/history/EXECUTIVE_SUMMARY.md` | Documentação histórica |
| `FINAL_VALIDATION_REPORT.md` | `docs/history/FINAL_VALIDATION_REPORT.md` | Documentação histórica |
| `PRACTICAL_VALIDATION_CHECKLIST.md` | `docs/history/PRACTICAL_VALIDATION_CHECKLIST.md` | Documentação histórica |
| `TIMEZONE_PADRONIZATION_REPORT.md` | `docs/history/TIMEZONE_PADRONIZATION_REPORT.md` | Documentação histórica |
| `REBUILD_VALIDATION_REPORT.md` | `docs/history/REBUILD_VALIDATION_REPORT.md` | Documentação histórica |
| `DOCUMENTATION_UPDATE.md` | `docs/history/DOCUMENTATION_UPDATE.md` | Documentação histórica |
| `docs/MAKEFILES-SUMMARY.md` | `docs/operations/makefiles-summary.md` | Documentação operacional |
| `docs/RESILIENCE_ANALYSIS_MAKE_VIDEO.md` | `docs/services/se5-make-video/resilience-analysis.md` | Documentação de serviço |

Esses movimentos nao esgotam a organizacao do repositório. Eles registram apenas a passada recente de reclassificacao da documentacao global.

---

## Convencoes de nomenclatura

### Documentacao (`.md`)
- `README.md` - indice ou ponto de entrada de area
- `kebab-case.md` - preferencia para novos arquivos em `docs/`
- nomes historicos existentes podem ser preservados quando o custo de renomear for alto

### Scripts (`.sh`, `.py`)
- `run_*.py` - Scripts runners
- `test_*.sh` - Scripts de teste
- `validate_*.py` - Scripts de validação
- `deploy*.sh` - Scripts de deploy
- `docker-*.sh` - Scripts Docker

### Testes (`test_*.py`)
- `test_unit_*.py` - Testes unitários
- `test_integration_*.py` - Testes de integração
- `test_e2e_*.py` - Testes end-to-end
- `conftest.py` - Configuração pytest

---

## 📊 Benefícios da Organização

### 1. **Navegação Intuitiva**
- Desenvolvedores sabem exatamente onde procurar
- Estrutura previsível em todos os serviços

### 2. **Separação de Responsabilidades**
- Código em `app/`
- Testes em `tests/`
- Documentação em `docs/`
- Scripts em `scripts/`

### 3. **CI/CD Otimizado**
- Paths previsíveis para automação
- Test discovery automático
- Build consistency

### 4. **Onboarding Rápido**
- Novos desenvolvedores entendem a estrutura imediatamente
- Documentação centralizada e acessível

### 5. **Manutenibilidade**
- Fácil localizar e modificar componentes
- Reduz duplicação acidental
- Facilita refactoring

---

## 🔄 Migrando para o Novo Padrão

Se você adicionar novos arquivos, siga estas diretrizes:

### Adicionando Documentação
```bash
# ❌ Errado
echo "# Novo Doc" > services/my-service/NEW_DOC.md

# ✅ Correto
echo "# Novo Doc" > services/my-service/docs/NEW_DOC.md
```

### Adicionando Scripts
```bash
# ❌ Errado
cp meu_script.sh services/my-service/

# ✅ Correto
cp meu_script.sh services/my-service/scripts/
chmod +x services/my-service/scripts/meu_script.sh
```

### Adicionando Testes
```bash
# ❌ Errado
echo "def test_foo(): pass" > services/my-service/test_foo.py

# ✅ Correto
echo "def test_foo(): pass" > services/my-service/tests/test_foo.py
```

---

## ✅ Checklist de Validação

Use este checklist ao criar/modificar um serviço:

- [ ] `README.md` é o único `.md` na raiz do serviço
- [ ] Todos os outros `.md` estão em `docs/`
- [ ] Todos os `.sh` estão em `scripts/`
- [ ] Todos os `test_*.py` estão em `tests/`
- [ ] `conftest.py` está em `tests/`
- [ ] Scripts auxiliares (`run_*.py`, `validate_*.py`) estão em `scripts/`
- [ ] Estrutura `app/`, `tests/`, `docs/`, `scripts/` existe
- [ ] `run.py` é o único entry point na raiz

---

## 🛠️ Ferramentas de Validação

### Script de Validação Automática

```bash
# Valida estrutura do projeto
./scripts/validate_structure.sh

# Valida estrutura de um serviço específico
./scripts/validate_structure.sh services/se5-make-video
```

### Pre-commit Hook

O projeto usa pre-commit hooks que validam:
- Arquivos `.md` fora de `docs/`
- Arquivos `.sh` fora de `scripts/`
- Arquivos `test_*.py` fora de `tests/`

---

## 📚 Referências

Este padrão segue as melhores práticas de:
- [The Twelve-Factor App](https://12factor.net/)
- [Google Engineering Practices](https://google.github.io/eng-practices/)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

---

## 🤝 Contribuindo

Ao contribuir com o projeto:
1. Siga esta estrutura rigorosamente
2. Execute `./scripts/validate_structure.sh` antes de commit
3. Documente qualquer exceção necessária
4. Mantenha consistência entre serviços

---

**Mantido por**: YTCaption Engineering Team  
**Aplicado em**: 2026-02-28  
**Versão**: 1.0.0
