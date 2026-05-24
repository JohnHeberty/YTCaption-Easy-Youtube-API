# 📖 Guia Rápido - Makefile

## 🎯 Visão Geral

Este Makefile padroniza **todos** os comandos do Make-Video Service. Substitui comandos longos e complexos por atalhos simples.

```bash
# Ver todos os comandos disponíveis
make help
```

---

## 🚀 Comandos Mais Usados

### **Desenvolvimento**

```bash
# Setup inicial
make dev-setup              # Instala dependências + valida estrutura

# Iniciar em modo dev (com rebuild)
make dev                    # docker compose up --build

# Ver logs em tempo real
make logs                   # docker compose logs -f

# Entrar no container
make shell                  # docker compose run --rm make-video /bin/bash
```

### **Testes**

```bash
# Testes rápidos (recomendado)
make test-quick             # Pula calibração, ~30s

# Testes completos
make test                   # Todos os testes, incluindo integração

# Validar imports apenas
make test-imports           # Verifica se todas as otimizações P0, P1, P2 estão acessíveis

# Cobertura de código
make test-coverage          # Gera relatório HTML em htmlcov/
```

### **Calibração OCR** 🎯

```bash
# CALIBRAÇÃO RÁPIDA (validação - 3-4 horas)
make calibrate-quick        # 5 trials apenas

# CALIBRAÇÃO COMPLETA (produção - 60-80 horas)
make calibrate              # 100 trials, otimização bayesiana
                            # Roda em background automaticamente

# Monitorar progresso
make calibrate-status       # Ver trials executados e melhor resultado
make cal-status             # Alias curto

# Ver relatório completo
make calibrate-report       # Markdown com métricas detalhadas

# Parar calibração
make calibrate-stop         # Kill processo + limpa PID

# Aplicar threshold otimizado
make calibrate-apply        # Atualiza .env automaticamente
make restart                # Reinicia serviço com novo threshold
```

### **Docker & Deploy**

```bash
# Build da imagem
make build                  # docker compose build

# Iniciar em background
make up                     # docker compose up -d

# Parar serviços
make down                   # docker compose down

# Reiniciar
make restart                # docker compose restart

# Status dos containers
make status                 # docker compose ps
make ps                     # Alias
```

### **Manutenção**

```bash
# Limpar cache Python
make clean                  # Remove __pycache__, *.pyc, etc.

# Limpar storage (⚠️ remove vídeos!)
make clean-storage          # Confirma antes de deletar

# Limpeza total
make clean-all              # Clean + down -v + docker prune
```

---

## 📊 Monitoramento

```bash
# Health check
make health                 # curl http://localhost:8005/health

# Métricas do sistema
make metrics                # Uso de disco + recursos Docker

# Verificar variáveis .env
make env-check              # Lista variáveis (valores mascarados)

# Ver configuração atual
make config                 # Mostra parâmetros do Makefile
```

---

## ⚡ Atalhos Rápidos

| Atalho | Comando Completo |
|--------|------------------|
| `make quick` | `make test-quick` |
| `make cal` | `make calibrate` |
| `make cal-status` | `make calibrate-status` |
| `make cal-apply` | `make calibrate-apply` |
| `make ps` | `make status` |

---

## 🎯 Workflows Comuns

### **Setup Inicial (Primeira Vez)**

```bash
make dev-setup              # Instala deps + valida estrutura
cp .env.example .env        # Configurar variáveis
make build                  # Build imagem Docker
make up                     # Iniciar serviços
make logs                   # Verificar inicialização
```

### **Desenvolvimento Diário**

```bash
make dev                    # Iniciar com rebuild
# ... fazer mudanças no código ...
make test-quick             # Testar rapidamente
make restart                # Aplicar mudanças
```

### **Executar Calibração**

```bash
# 1. Validação rápida primeiro
make calibrate-quick        # 3-4 horas, ~5 trials

# 2. Se accuracy > 20%, rodar completa
make calibrate              # 60-80 horas, 100 trials

# 3. Monitorar em outra janela
watch -n 60 make cal-status # Atualiza a cada 60s

# 4. Quando concluir, aplicar resultado
make calibrate-apply        # Atualiza .env
make restart                # Reiniciar com novo threshold
```

### **Deploy em Produção**

```bash
# Opção 1: Deploy rápido
make prod-deploy            # Build + up automaticamente

# Opção 2: Manual
make build
make up
make health                 # Verificar health
make logs                   # Monitorar inicialização
```

### **Troubleshooting**

```bash
# Validar configuração
make validate               # Checa estrutura + arquivos

# Ver logs
make logs                   # Tempo real

# Reiniciar containers
make restart                # Soft restart
make down && make up        # Hard restart

# Limpeza se algo quebrou
make clean-all              # Remove tudo e recomeça
make build
make up
```

---

## 📋 Tabela de Referência Rápida

| Categoria | Comandos |
|-----------|----------|
| **Help** | `help` |
| **Dev** | `install`, `dev`, `logs`, `shell`, `dev-setup` |
| **Testes** | `test`, `test-quick`, `test-imports`, `test-coverage`, `full-test` |
| **Calibração** | `calibrate`, `calibrate-quick`, `calibrate-status`, `calibrate-stop`, `calibrate-apply`, `calibrate-report` |
| **Docker** | `build`, `up`, `down`, `restart`, `status` |
| **Manutenção** | `clean`, `clean-storage`, `clean-all`, `validate` |
| **Monitoring** | `health`, `metrics`, `env-check`, `config`, `version` |
| **Atalhos** | `quick`, `cal`, `cal-status`, `cal-apply`, `ps` |

---

## 🔧 Personalização

### Variáveis Configuráveis

Edite o `Makefile` para ajustar:

```makefile
OPTUNA_TRIALS := 100        # Número de trials na calibração
OPTUNA_TIMEOUT := 7200      # Timeout por trial (segundos)
ORPHAN_THRESHOLD := 5       # Minutos para detectar job órfão
```

### Adicionar Novos Comandos

```makefile
my-command: ## Descrição do comando
	@echo "Executando meu comando..."
	# ... comandos ...
```

---

## ❓ FAQ

**Q: Como ver apenas os comandos de calibração?**
```bash
make help | grep calibrate
```

**Q: Como rodar calibração com mais trials?**
```bash
# Editar Makefile linha 22:
OPTUNA_TRIALS := 200
```

**Q: Como ver logs da calibração em background?**
```bash
tail -f /tmp/optuna_full.log
```

**Q: Como cancelar calibração se demorar demais?**
```bash
make calibrate-stop
```

**Q: O make calibrate-apply não funcionou?**
```bash
# Verificar se há resultado:
cat storage/calibration/trsd_optuna_best_params.json

# Atualizar .env manualmente:
echo "OCR_CONFIDENCE_THRESHOLD=0.55" >> .env
make restart
```

---

## 📚 Documentação Relacionada

- **UNION_OPTIMIZE.md** - Documentação completa de otimizações
- **README.md** - Visão geral do serviço
- **QUICKSTART.md** - Guia de início rápido

---

## 💡 Dicas

1. **Use `make help` sempre** que esquecer um comando
2. **`make validate`** antes de fazer deploy
3. **`make test-quick`** antes de commit
4. **`make calibrate-quick`** antes de rodar completa
5. **`make cal-status`** para ver progresso da calibração
6. **Atalhos** economizam digitação (ex: `make cal` ao invés de `make calibrate`)

---

**Última Atualização:** 11/02/2026  
**Versão:** 2.1
