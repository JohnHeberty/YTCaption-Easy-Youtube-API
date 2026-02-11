#!/bin/bash
# Monitor Optuna Calibration Progress - Enhanced Version
# Usage: ./monitor_calibration.sh [--watch] [--json]
#
# Options:
#   --watch   Atualiza automaticamente a cada 10s
#   --json    Saída em formato JSON

set -e

LOG_FILE="/tmp/optuna_full.log"
RESULTS_FILE="storage/calibration/optuna_incremental_results.json"
TARGET_ACCURACY=90  # Meta de acurácia em %
TOTAL_TRIALS=100    # Total planejado de trials

# Cores para terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções auxiliares
print_header() {
    clear
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}         🔬 MONITOR DE CALIBRAÇÃO OPTUNA - EasyOCR/TRSD          ${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

get_memory_usage() {
    # Uso de memória do processo Optuna
    if pgrep -f "calibrate_trsd_optuna" > /dev/null; then
        pid=$(pgrep -f "calibrate_trsd_optuna" | head -1)
        mem=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.1f", $1/1024}')
        echo "${mem}MB"
    else
        echo "N/A"
    fi
}

calculate_eta() {
    local completed=$1
    local total=$2
    local start_time=$3
    
    if [ "$completed" -gt 0 ] && [ -n "$start_time" ]; then
        now=$(date +%s)
        elapsed=$((now - start_time))
        per_trial=$((elapsed / completed))
        remaining=$((total - completed))
        eta_seconds=$((per_trial * remaining))
        
        if [ $eta_seconds -gt 3600 ]; then
            echo "$((eta_seconds / 3600))h $((eta_seconds % 3600 / 60))m"
        elif [ $eta_seconds -gt 60 ]; then
            echo "$((eta_seconds / 60))m $((eta_seconds % 60))s"
        else
            echo "${eta_seconds}s"
        fi
    else
        echo "Calculando..."
    fi
}

print_progress_bar() {
    local current=$1
    local total=$2
    local width=40
    
    local percent=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    printf "["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "] %3d%% (%d/%d)\n" "$percent" "$current" "$total"
}

print_accuracy_chart() {
    if [ -f "$RESULTS_FILE" ]; then
        echo "📈 Histórico de Acurácia (últimos 10 trials):"
        echo ""
        # Gráfico ASCII simples
        jq -r '.trials[-10:] | .[] | "\(.trial_number)|\(.metrics.accuracy * 100)"' "$RESULTS_FILE" 2>/dev/null | while IFS='|' read -r trial acc; do
            acc_int=${acc%.*}
            bar_len=$((acc_int / 5))
            printf "   T%02d |" "$trial"
            for i in $(seq 1 $bar_len); do printf "▓"; done
            printf " %.1f%%\n" "$acc"
        done || echo "   Sem dados suficientes"
        echo ""
    fi
}

# Main monitor function
run_monitor() {
    print_header
    
    # 1. STATUS DO PROCESSO
    echo -e "${YELLOW}► PROCESSO${NC}"
    echo "────────────────────────────"
    
    if pgrep -f "calibrate_trsd_optuna" > /dev/null; then
        pid=$(pgrep -f "calibrate_trsd_optuna" | head -1)
        mem=$(get_memory_usage)
        uptime_raw=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
        echo -e "   Status:    ${GREEN}● RODANDO${NC} (PID: $pid)"
        echo "   Memória:   $mem"
        echo "   Uptime:    $uptime_raw"
    else
        echo -e "   Status:    ${RED}○ PARADO${NC}"
    fi
    
    echo ""
    
    # 2. PROGRESSO DA CALIBRAÇÃO
    echo -e "${YELLOW}► PROGRESSO${NC}"
    echo "────────────────────────────"
    
    if [ -f "$RESULTS_FILE" ]; then
        trials_count=$(jq '.trials | length' "$RESULTS_FILE" 2>/dev/null || echo "0")
        best_accuracy=$(jq '.best_trial.metrics.accuracy // 0' "$RESULTS_FILE" 2>/dev/null)
        best_threshold=$(jq '.best_trial.params.min_confidence // "N/A"' "$RESULTS_FILE" 2>/dev/null)
        best_precision=$(jq '.best_trial.metrics.precision // 0' "$RESULTS_FILE" 2>/dev/null)
        best_recall=$(jq '.best_trial.metrics.recall // 0' "$RESULTS_FILE" 2>/dev/null)
        
        echo -n "   Trials:    "
        print_progress_bar "$trials_count" "$TOTAL_TRIALS"
        
        # ETA calculation (simplificado)
        if [ "$trials_count" -gt 0 ]; then
            echo "   ETA:       $(calculate_eta "$trials_count" "$TOTAL_TRIALS" "$(date -d '-30 minutes' +%s)")"
        fi
        
        echo ""
        echo -e "${YELLOW}► MELHOR RESULTADO${NC}"
        echo "────────────────────────────"
        
        acc_pct=$(echo "$best_accuracy * 100" | bc -l 2>/dev/null | cut -c1-5 || echo "0")
        prec_pct=$(echo "$best_precision * 100" | bc -l 2>/dev/null | cut -c1-5 || echo "0")
        rec_pct=$(echo "$best_recall * 100" | bc -l 2>/dev/null | cut -c1-5 || echo "0")
        
        if (( $(echo "$acc_pct >= $TARGET_ACCURACY" | bc -l) )); then
            echo -e "   Accuracy:  ${GREEN}${acc_pct}%${NC} ✓ META ATINGIDA!"
        else
            echo -e "   Accuracy:  ${YELLOW}${acc_pct}%${NC} (meta: ${TARGET_ACCURACY}%)"
        fi
        
        echo "   Precision: ${prec_pct}%"
        echo "   Recall:    ${rec_pct}%"
        echo "   Threshold: $best_threshold"
        
        echo ""
        
        # 3. GRÁFICO DE HISTÓRICO
        print_accuracy_chart
        
        # 4. ÚLTIMOS TRIALS
        echo -e "${YELLOW}► ÚLTIMOS 5 TRIALS${NC}"
        echo "────────────────────────────"
        jq -r '.trials[-5:] | .[] | "   #\(.trial_number|tostring|.[0:2]) threshold=\(.params.min_confidence) → acc=\(.metrics.accuracy*100|floor)% prec=\(.metrics.precision*100|floor)% rec=\(.metrics.recall*100|floor)%"' "$RESULTS_FILE" 2>/dev/null || echo "   Sem dados"
        
    else
        echo "   Aguardando início da calibração..."
    fi
    
    echo ""
    
    # 5. LOG ATIVIDADE
    echo -e "${YELLOW}► ATIVIDADE RECENTE${NC}"
    echo "────────────────────────────"
    if [ -f "$LOG_FILE" ]; then
        tail -8 "$LOG_FILE" 2>/dev/null | grep -E "(Converting|Converted|Trial|Accuracy|VALIDAÇÃO|CALIBRAÇÃO|Best|PASSOU|Error)" | tail -5 | sed 's/^/   /' || echo "   Processando..."
    else
        echo "   Log não encontrado"
    fi
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "💡 Comandos: tail -f /tmp/optuna_full.log | pkill -f calibrate_trsd_optuna"
}

# Modo watch
if [[ "$1" == "--watch" ]]; then
    while true; do
        run_monitor
        echo ""
        echo "Atualizando em 10s... (Ctrl+C para sair)"
        sleep 10
    done
elif [[ "$1" == "--json" ]]; then
    # Saída JSON para integração
    if [ -f "$RESULTS_FILE" ]; then
        jq '{
            status: (if '"$(pgrep -f calibrate_trsd_optuna > /dev/null && echo "true" || echo "false")"' then "running" else "stopped" end),
            trials_completed: (.trials | length),
            trials_total: '$TOTAL_TRIALS',
            best_accuracy: .best_trial.metrics.accuracy,
            best_threshold: .best_trial.params.min_confidence,
            target_accuracy: '$TARGET_ACCURACY'
        }' "$RESULTS_FILE"
    else
        echo '{"status": "not_started", "trials_completed": 0}'
    fi
else
    run_monitor
fi
