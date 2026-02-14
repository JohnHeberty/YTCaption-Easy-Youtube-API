# 🎯 Pipeline de Calibração Automática - EasyOCR

## 📋 Visão Geral

Sistema automatizado de calibração que:
1. **Converte vídeos AV1 → H.264** (Opção A - evita problemas de performance)
2. **Testa com 5 trials** (validação rápida)  
3. **Se validação passar → executa 100 trials** (calibração completa)

---

## 🚀 Execução

### Modo Automático (Recomendado)

```bash
cd services/make-video

# Executar pipeline completa em background
nohup docker compose run --rm \
  -v "$(pwd):/app:ro" \
  -v "$(pwd)/storage:/app/storage:rw" \
  make-video python calibrate_trsd_optuna.py \
  > /tmp/optuna_full.log 2>&1 &

# Monitorar progresso
./monitor_calibration.sh
```

### Personalizar Trials

```bash
# Mais trials = melhor resultado (mais lento)
export OPTUNA_TRIALS=200
export OPTUNA_TIMEOUT=7200  # 2 horas

docker compose run --rm \
  -v "$(pwd):/app:ro" \
  -v "$(pwd)/storage:/app/storage:rw" \
  make-video python calibrate_trsd_optuna.py
```

---

## ⏱️ Tempo Estimado

| Fase | Duração | Descrição |
|------|---------|-----------|
| **Conversão AV1→H.264** | ~5 min | 11 vídeos AV1 convertidos |
| **Validação (5 trials)** | ~3-4 horas | Teste rápido de funcionamento |
| **Calibração (100 trials)** | ~60-80 horas | Otimização completa (se validação passar) |

💡 **Dica**: Rode overnight ou em servidor dedicado

---

## 📊 Monitoramento em Tempo Real

### Script de Monitoramento

```bash
# Ver status completo
./monitor_calibration.sh

# Saída exemplo:
# ✅ Processo ativo
# 📊 PROGRESSO ATUAL:
#    Trials completados: 3
#    Melhor Accuracy: 72.2%
#    Melhor threshold: 0.55
```

### Comandos Úteis

```bash
# Log completo em tempo real
tail -f /tmp/optuna_full.log

# Ver conversões H.264
tail /tmp/optuna_full.log | grep -E "Converting|Converted"

# Ver progresso dos trials
tail /tmp/optuna_full.log | grep "Trial.*Accuracy"

# Parar processo
pkill -f calibrate_trsd_optuna
```

### Resultados Incrementais

Arquivo: `storage/calibration/optuna_incremental_results.json`

```bash
# Ver melhor resultado até agora
cat storage/calibration/optuna_incremental_results.json | jq '.best_trial'

# Contar trials completados
cat storage/calibration/optuna_incremental_results.json | jq '.trials | length'

# Ver últimos 3 trials
cat storage/calibration/optuna_incremental_results.json | \
  jq '.trials[-3:] | .[] | {trial: .trial_number, accuracy: .metrics.accuracy, threshold: .params.min_confidence}'
```

---

## ✅ Validação (5 Trials)

**Critério de Aprovação**: `accuracy > 0%`

### Se PASSAR (✅)
```
✅ VALIDAÇÃO PASSOU! Prosseguindo com calibração completa...
🚀 CALIBRAÇÃO COMPLETA (100 trials)
```
→ Continua automaticamente para 100 trials

### Se FALHAR (❌)
```
❌ VALIDAÇÃO FALHOU!
   Todos os 5 trials resultaram em accuracy 0%
   Possíveis causas:
   - Vídeos não foram processados corretamente
   - Problemas de codec ainda presentes
   - Dataset muito desbalanceado
🛑 Abortando calibração completa
```
→ Processo para, requer investigação manual

---

## 📁 Arquivos Gerados

### Durante o Processo

```
storage/
├── calibration/
│   ├── h264_converted/          # Vídeos convertidos (temporários)
│   │   ├── OK/
│   │   │   └── *.mp4           # Vídeos OK em H.264
│   │   └── NOT_OK/
│   │       └── *.mp4           # Vídeos NOT_OK em H.264
│   │
│   └── optuna_incremental_results.json  # ⭐ Resultados salvos a cada trial
```

### Ao Finalizar

```
storage/calibration/
├── trsd_optuna_best_params.json      # ⭐ Melhor configuração encontrada
├── trsd_optuna_report.md             # 📄 Relatório markdown
└── optuna_incremental_results.json   # 📊 Histórico completo
```

---

## 🎯 Aplicar Melhor Threshold

Após calibração completa:

```bash
# Ver melhor threshold
cat storage/calibration/trsd_optuna_best_params.json | jq '.best_params.min_confidence'

# Exemplo: 0.55
```

**Aplicar em produção:**

```python
# Editar: app/ocr_detector.py (linha ~90)
def detect_subtitle_in_frame(self, frame, min_confidence=55.0):  # ← Usar valor encontrado
```

Ou usar variável de ambiente:
```bash
export OCR_MIN_CONFIDENCE=55.0
docker compose up -d
```

---

## 🔧 Opção A - Conversão AV1 → H.264

### Por que converter?

| Codec | Performance CPU | Observação |
|-------|----------------|------------|
| **H.264** | ⚡ Rápido (~2min/vídeo) | Otimizado, amplamente suportado |
| **AV1** | 🐌 Muito lento (~40min/vídeo) | EasyOCR sem aceleração GPU |

### O que é convertido

```bash
# Verificar codecs do dataset
for f in storage/{OK,NOT_OK}/*.mp4; do
  codec=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name \
    -of default=noprint_wrappers=1:nokey=1 "$f" 2>&1)
  echo "$(basename $f): $codec"
done
```

**Conversão automática:**
- ✅ AV1 → H.264 (sempre)
- ✅ Altri codecs lentos → H.264
- ⏭️ H.264 → mantido (já otimizado)

### Desativar Conversão (NÃO RECOMENDADO)

```python
# calibrate_trsd_optuna.py (linha ~420)
optimizer = TRSDOptimizer(
    ok_dir=str(OK_DIR),
    not_ok_dir=str(NOT_OK_DIR),
    convert_to_h264=False  # ← Desativar (trials muito lentos!)
)
```

---

## 📈 Resultados Esperados

### Baseline Atual
```
Threshold: 60.0 (padrão)
Accuracy:  70.0%
Precision: 100% ✅ (zero falsos positivos)
Recall:    60.0%
```

### Meta com Optuna
```
Threshold: ? (a ser otimizado)
Accuracy:  ≥90%  🎯
Precision: ≥95%
Recall:    ≥85%
```

---

## 🐛 Troubleshooting

### Processo travou durante conversão

```bash
# Ver log de erros
tail -100 /tmp/optuna_full.log | grep -i error

# Verificar vídeos convertidos
ls -lh storage/calibration/h264_converted/{OK,NOT_OK}/
```

### Accuracy sempre 0%

**Causas possíveis:**
1. Dataset vazio ou inacessível
2. Permissões de arquivo (volumes Docker)
3. EasyOCR não inicializou

**Diagnóstico:**
```bash
# Verificar dataset
ls storage/{OK,NOT_OK}/*.mp4 | wc -l  # Deve ser >0

# Testar EasyOCR manualmente
docker compose run --rm make-video python -c \
  "from app.ocr_detector import OCRDetector; d=OCRDetector(); print('✅ OK')"
```

### Conversão muito lenta

```bash
# Converter apenas subset
mkdir -p storage_subset/{OK,NOT_OK}
cp storage/OK/*.mp4 storage_subset/OK/ | head -5
cp storage/NOT_OK/*.mp4 storage_subset/NOT_OK/ | head -10

# Editar calibrate_trsd_optuna.py e apontar para storage_subset
```

---

## �️ Execução no Backend (Servidor)

### Preparação

```bash
# Conectar ao servidor via SSH
ssh user@seu-servidor.com

# Navegar para o diretório
cd /path/to/YTCaption-Easy-Youtube-API/services/make-video

# Verificar Docker está rodando
docker info
```

### Execução com Screen/Tmux (Recomendado)

```bash
# Iniciar sessão screen para persistir após logout
screen -S optuna

# Dentro da sessão screen:
nohup docker compose run --rm \
  -v "$(pwd):/app:ro" \
  -v "$(pwd)/storage:/app/storage:rw" \
  make-video python calibrate_trsd_optuna.py \
  > /tmp/optuna_full.log 2>&1 &

# Executar monitor
./monitor_calibration.sh --watch

# Desanexar da sessão: Ctrl+A, depois D
# Reconectar depois: screen -r optuna
```

### Execução com systemd (Produção)

Criar serviço systemd:

```bash
sudo tee /etc/systemd/system/optuna-calibration.service << 'EOF'
[Unit]
Description=Optuna Calibration for EasyOCR
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/path/to/services/make-video
ExecStart=/usr/bin/docker compose run --rm \
  -v /path/to/services/make-video:/app:ro \
  -v /path/to/services/make-video/storage:/app/storage:rw \
  make-video python calibrate_trsd_optuna.py
Restart=no
StandardOutput=file:/tmp/optuna_full.log
StandardError=file:/tmp/optuna_full.log

[Install]
WantedBy=multi-user.target
EOF

# Iniciar
sudo systemctl daemon-reload
sudo systemctl start optuna-calibration

# Ver status
sudo systemctl status optuna-calibration

# Ver logs
journalctl -u optuna-calibration -f
```

### Monitoramento Remoto

```bash
# Em outra sessão SSH:
cd /path/to/services/make-video

# Monitor com atualização automática
./monitor_calibration.sh --watch

# Ou saída JSON para integração
./monitor_calibration.sh --json | jq .
```

---

## �📞 Suporte

**Logs importantes:**
- `/tmp/optuna_full.log` - Log completo da execução
- `storage/calibration/optuna_incremental_results.json` - Resultados salvos

**Verificar status:**
```bash
./monitor_calibration.sh
```

**Issues conhecidos:**
- AV1 codec é extremamente lento → Opção A resolve
- GPU não disponível → CPU-only é esperado e funcional
- Memória insuficiente → Docker configurado com 6GB limite

---

## 🎓 Documentação Adicional

- [EasyOCR Documentation](https://github.com/JaidedAI/EasyOCR)
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [FFmpeg H.264 Encoding Guide](https://trac.ffmpeg.org/wiki/Encode/H.264)
