#!/bin/bash
# Quick Start - Optuna Optimized Calibration

echo "═══════════════════════════════════════════════════════════"
echo "🎯 Calibração Optuna - Parâmetros Otimizados"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📊 PARÂMETROS EXPANDIDOS (6 parâmetros):"
echo ""
echo "  1. min_confidence:      0.30 → 0.90  (começando em 0.30!)"
echo "  2. frame_threshold:     0.20 → 0.50"
echo "  3. max_samples:         8 → 15 frames"
echo "  4. sample_interval:     1.5 → 3.0 segundos"
echo "  5. det_db_thresh:       0.2 → 0.5"
echo "  6. det_db_box_thresh:   0.4 → 0.7"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 INICIAR CALIBRAÇÃO:"
echo ""
echo "  Opção 1 (COMPLETA):  make calibrate-start   # 100 trials, ~60-80h"
echo "  Opção 2 (RÁPIDA):    make calibrate-quick   # 5 trials, ~3-4h"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📈 MONITORAMENTO:"
echo ""
echo "  make cal-status    # Ver status atual"
echo "  make cal-logs      # Logs em tempo real (Ctrl+C para sair)"
echo "  make cal-watch     # Monitoramento contínuo (atualiza 30s)"
echo "  make cal-stop      # Parar calibração"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💾 RESULTADOS SALVOS EM:"
echo ""
echo "  storage/calibration/optuna_incremental_results.json"
echo "  storage/calibration/trsd_optuna_best_params.json"
echo "  storage/calibration/trsd_optuna_report.md"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# Ask user which option
read -p "🎯 Escolha uma opção (1=COMPLETA, 2=RÁPIDA, Enter=Cancelar): " choice

case "$choice" in
    1)
        echo ""
        echo "🚀 Iniciando calibração COMPLETA..."
        make calibrate-start
        ;;
    2)
        echo ""
        echo "⚡ Iniciando calibração RÁPIDA..."
        make calibrate-quick
        ;;
    *)
        echo ""
        echo "❌ Cancelado"
        exit 0
        ;;
esac
