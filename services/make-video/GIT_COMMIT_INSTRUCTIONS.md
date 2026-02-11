# 📦 Instruções Git - Commit e Push

## Status Atual

Você tem:
- **13 arquivos modificados**
- **12 arquivos novos**
- **3 arquivos deletados** (movidos para trash)

---

## Passo a Passo

### 1. Verificar mudanças
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
git status
```

### 2. Adicionar todos os arquivos
```bash
git add -A
```

### 3. Verificar o que será commitado
```bash
git status
```

### 4. Fazer o commit
```bash
git commit -m "feat(make-video): EasyOCR migration + Optuna calibration pipeline

BREAKING CHANGES:
- Migração de Tesseract para EasyOCR
- Novo sistema de calibração via Optuna

Features:
- EasyOCR reader (PT/EN) com validação por dicionário
- Conversão automática AV1→H.264 para performance
- Calibração com validação em 5 trials antes de 100 completos
- Salvamento incremental de resultados JSON
- Monitor visual com progress bar e ETA

Bug Fixes:
- CRÍTICO: min_confidence threshold agora é aplicado (antes era ignorado)

Documentação:
- CALIBRATION_GUIDE.md: guia completo de calibração
- OPTIMIZE.md: oportunidades de otimização identificadas

Reorganização:
- Arquivos obsoletos movidos para trash/
- Pasta trash/ adicionada ao .gitignore"
```

### 5. Push para o remoto
```bash
git push origin main
```

---

## Commit Alternativo (Mais Curto)

Se preferir uma mensagem mais simples:

```bash
git commit -m "feat: EasyOCR migration, Optuna calibration, bug fixes

- Migrate from Tesseract to EasyOCR
- Add automatic AV1→H.264 conversion
- Fix critical threshold bug
- Add calibration guide and optimization docs"
```

---

## Comandos de Verificação

```bash
# Ver log do último commit
git log -1 --oneline

# Ver diferenças staged
git diff --staged --stat

# Ver branches
git branch -vv

# Ver remote
git remote -v
```

---

## Em caso de conflitos

```bash
# Buscar últimas mudanças do remoto
git fetch origin

# Rebase se necessário
git rebase origin/main

# Resolver conflitos e continuar
git rebase --continue

# Ou abortar se necessário
git rebase --abort
```

---

## Arquivos Importantes Neste Commit

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `app/ocr_detector.py` | Modificado | EasyOCR reader + BUG FIX threshold |
| `calibrate_trsd_optuna.py` | Novo | Pipeline de calibração Optuna |
| `monitor_calibration.sh` | Novo | Monitor visual de progresso |
| `CALIBRATION_GUIDE.md` | Novo | Documentação completa |
| `OPTIMIZE.md` | Novo | Oportunidades de otimização |
| `.gitignore` | Modificado | Adiciona pasta trash/ |

---

> **Data:** Auto-gerado
