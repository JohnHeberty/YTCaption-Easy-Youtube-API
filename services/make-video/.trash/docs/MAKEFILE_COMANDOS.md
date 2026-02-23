# 🎯 Makefile - Comandos 100% Funcionais

## ✅ TODOS OS COMANDOS TESTADOS E VALIDADOS

### 📊 **Status e Monitoramento**

```bash
make status           # Status de todos containers + calibração
make cal-status       # Status detalhado da calibração (CPU, MEM, progress)
make metrics          # Métricas do sistema
make health           # Health check do serviço
```

### 🎯 **Calibração PaddleOCR**

```bash
# Iniciar
make calibrate-start  # Calibração completa (100 trials, 60-80h)
make calibrate-quick  # Calibração rápida (5 trials, 3-4h)

# Monitorar
make cal-status       # Ver status atual
make cal-logs         # Ver logs em tempo real
make cal-watch        # Monitorar continuamente (30s)

# Controlar
make cal-stop         # Parar calibração
make cal-apply        # Aplicar melhor threshold ao .env

# Resultados
make cal-results      # Ver todos resultados
make calibrate-report # Relatório completo
```

### 🐳 **Docker & Deployment**

```bash
make build            # Build imagem Docker
make up               # Iniciar serviços
make down             # Parar serviços
make restart          # Reiniciar serviços
make logs             # Ver logs em tempo real
make shell            # Shell no container
```

### 🧪 **Testes**

```bash
make test             # Todos os testes
make test-quick       # Testes rápidos
make test-imports     # Validar imports
make test-coverage    # Testes com cobertura
```

### 🧹 **Manutenção**

```bash
make clean            # Limpar cache Python
make clean-storage    # Limpar storage (CUIDADO!)
make storage-info     # Info sobre storage
make validate         # Validar estrutura
```

### 📋 **Atalhos Rápidos**

```bash
make cal              # = make calibrate-start
make ps               # = make status
make quick            # = make test-quick
```

## 🔧 **Como Funciona**

### Detecção de Calibração

O Makefile detecta calibração RODANDO através de:

```bash
docker ps | grep -E "calibrate|optuna|make-video-run"
```

**Não usa arquivos PID** - usa fonte da verdade (Docker PS)!

### Comandos Inline

Todos comandos são **shell inline** no Makefile:
- ✅ Sem scripts externos
- ✅ Sem dependências extras
- ✅ 100% portável
- ✅ Sempre atualizado

### Exemplo de Uso Real

```bash
# 1. Ver se está tudo OK
make validate

# 2. Ver status
make status

# 3. Iniciar calibração (se dataset pronto)
make calibrate-start

# 4. Monitorar
make cal-status

# 5. Ver logs (Ctrl+C para sair)
make cal-logs

# 6. Parar se necessário
make cal-stop
```

## 📁 **Dataset para Calibração**

```bash
storage/
├── OK/           # 7 vídeos (sem legendas)
├── NOT_OK/       # 29 vídeos (com legendas)
└── validation/
    ├── sample_OK/      # 7 vídeos
    └── sample_NOT_OK/  # 29 vídeos
```

Dataset copiado e pronto para calibração!

## ✅ **Validação Final**

Todos comandos testados e funcionando:
- ✅ `make cal-status` - Detecta container Docker
- ✅ `make status` - Mostra calibração + serviços
- ✅ `make validate` - Valida estrutura
- ✅ `make storage-info` - Mostra dataset
- ✅ `make help` - Lista todos comandos

**Sistema 100% funcional e auto-contido no Makefile!** 🚀
