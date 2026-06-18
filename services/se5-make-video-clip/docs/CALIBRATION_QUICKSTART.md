# 🎯 Guia Rápido - Calibração OCR

**Calibração automática de threshold via Optuna rodando em background**

> **📖 TL;DR:**  
> `make calibrate-start` → `make calibrate-watch` → `make calibrate-apply` → `make restart`

---

## 🚀 Início Rápido (3 Passos)

### 1️⃣ Iniciar Calibração

```bash
cd services/se5-make-video
make calibrate-start
# ou: make cal-start (alias curto)
```

### 2️⃣ Acompanhar Progresso

```bash
make calibrate-watch
# ou: make cal-watch (alias curto)
```

**Atualiza automaticamente a cada 30 segundos!**

### 3️⃣ Aplicar Resultado

```bash
make calibrate-apply && make restart
# ou: make cal-apply && make restart
```

**Pronto! 🎉**

---

## 👁️ Acompanhar Progresso

### Opção 1: Status Rápido

```bash
make calibrate-status
make cal-status  # alias curto
```

**Mostra:**
- ✅ Status do processo (ativo/parado)
- 🕐 Tempo decorrido
- 📊 Progresso (X/100 trials)
- 📈 Percentual completado
- 🎯 Melhor resultado até agora

### Opção 2: Monitoramento Contínuo (Auto-atualiza a cada 30s)

```bash
make calibrate-watch
make cal-watch  # alias curto
```

**Ideal para deixar rodando em terminal dedicado!**

### Opção 3: Ver Logs em Tempo Real

```bash
make calibrate-logs
make cal-logs  # alias curto
```

**Mostra o output completo** do Optuna conforme ele executa.

---

## 📊 Ver Resultados

### Ver Melhor Threshold Encontrado

```bash
make calibrate-status  # Mostra resumo
cat storage/calibration/trsd_optuna_best_params.json | jq .
```

### Ver Todos os Resultados

```bash
make calibrate-results
```

### Ver Relatório Completo

```bash
make calibrate-report
cat storage/calibration/trsd_optuna_report.md
```

---

## ✅ Aplicar Threshold Otimizado

Após a calibração completar (ou quando achar que já tem resultados bons):

```bash
make calibrate-apply
make cal-apply  # alias curto
```

**Isso irá:**
1. Ler o melhor threshold de `storage/calibration/trsd_optuna_best_params.json`
2. Atualizar `.env` com `OCR_CONFIDENCE_THRESHOLD=<valor>`
3. Avisar para reiniciar o serviço

**Reiniciar serviço:**
```bash
make restart
```

---

## 🛑 Parar Calibração

Se precisar interromper a calibração:

```bash
make calibrate-stop
make cal-stop  # alias curto
```

**Os resultados parciais são salvos** e podem ser usados.

---

## 🧹 Limpeza

### Limpar Logs e PIDs (mantém resultados)

```bash
make calibrate-clean
```

### Remover TUDO (incluindo resultados)

```bash
rm -rf storage/calibration/*
rm -f /tmp/calibration.pid /tmp/calibration_start.txt /tmp/optuna_full.log
```

---

## 📋 Exemplo de Fluxo Completo

```bash
# 1. Iniciar calibração
cd services/se5-make-video
make calibrate-start

# 2. Em outro terminal, monitorar continuamente
make calibrate-watch
# ou ver logs em tempo real
make calibrate-logs

# 3. Verificar status periodicamente
make calibrate-status

# 4. Após conclusão (ou quando satisfeito), aplicar threshold
make calibrate-apply

# 5. Reiniciar serviço para usar novo threshold
make restart

# 6. Validar que está funcionando
make health
```

---

## ⚡ Calibração Rápida (Teste)

Para testar o pipeline antes de rodar 100 trials:

```bash
make calibrate-quick  # 5 trials, ~3-4h
```

**Não roda em background** - use para validação.

---

## 📂 Arquivos Importantes

| Arquivo | Descrição |
|---------|-----------|
| `/tmp/calibration.pid` | PID do processo de calibração |
| `/tmp/calibration_start.txt` | Timestamp de início |
| `/tmp/optuna_full.log` | Logs completos da execução |
| `storage/calibration/trsd_optuna_best_params.json` | Melhor threshold encontrado |
| `storage/calibration/optuna_incremental_results.json` | Resultados incrementais |
| `storage/calibration/trsd_optuna_report.md` | Relatório final |

---

## 🔧 Troubleshooting

### Calibração não inicia

```bash
# Verificar se já tem uma rodando
make calibrate-status

# Limpar estado anterior
make calibrate-clean

# Tentar novamente
make calibrate-start
```

### Processo travou

```bash
# Forçar parada
make calibrate-stop

# Verificar logs
tail -100 /tmp/optuna_full.log

# Limpar e reiniciar
make calibrate-clean
make calibrate-start
```

### Sem resultados após muito tempo

```bash
# Ver progresso nos logs
make calibrate-logs

# Verificar se processo está vivo
make calibrate-status
ps aux | grep calibrate_trsd_optuna.py
```

---

## 🎯 Dicas

1. **Use terminal multiplexer (tmux/screen)**  
   Para não perder o processo se desconectar da sessão SSH

2. **Monitore espaço em disco**  
   Calibração gera vídeos convertidos temporários

3. **Deixe rodar overnight**  
   100 trials leva 60-80 horas (2.5-3 dias)

4. **Resultados salvos incrementalmente**  
   Pode parar a qualquer momento e usar resultados parciais

5. **Calibração rápida primeiro**  
   `make calibrate-quick` valida que tudo funciona (3-4h)

---

## 📊 Resultados Esperados

**Baseline (sem calibração):**
```
Threshold: 0.40
Accuracy:  ~70%
```

**Após calibração (esperado):**
```
Threshold: ~0.55 (otimizado)
Accuracy:  ≥90% 🎯
Precision: ≥95%
Recall:    ≥85%
F1-Score:  ≥90%
```

---

## 🆘 Suporte

**Ver todos os comandos:**
```bash
make help
```

**Documentação completa:**
- [UNION_OPTIMIZE.md](UNION_OPTIMIZE.md) - Roadmap completo
- [README.md](README.md) - Documentação geral
