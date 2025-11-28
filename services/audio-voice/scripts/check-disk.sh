#!/bin/bash
###############################################################################
# check-disk.sh - Monitor de espaço em disco para produção
# 
# Uso: ./check-disk.sh [THRESHOLD]
# Exemplo: ./check-disk.sh 80
#
# Adicionar ao crontab:
# */15 * * * * /usr/local/bin/check-disk.sh 80
###############################################################################

THRESHOLD=${1:-80}
LOG_FILE="/var/log/disk-monitor.log"
ALERT_EMAIL="${ALERT_EMAIL:-admin@example.com}"

# Cores para output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Função de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Verifica uso da partição raiz
check_root_partition() {
    local usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    local partition=$(df / | tail -1 | awk '{print $1}')
    
    log "Partição raiz ($partition): ${usage}% usado"
    
    if [ "$usage" -gt "$THRESHOLD" ]; then
        echo -e "${RED}⚠️  ALERTA: Disco raiz em ${usage}% de uso!${NC}"
        
        # Mostra maiores consumidores
        log "Top 10 consumidores de espaço na raiz:"
        du -hx / 2>/dev/null | sort -rh | head -10 | tee -a "$LOG_FILE"
        
        # Envia alerta por email (se mail estiver configurado)
        if command -v mail &> /dev/null; then
            echo "Disco raiz em ${usage}% de uso. Limpar imediatamente!" | \
                mail -s "⚠️ ALERTA: Disco Raiz Crítico (${usage}%)" "$ALERT_EMAIL"
        fi
        
        return 1
    else
        echo -e "${GREEN}✓ Disco raiz OK: ${usage}% usado${NC}"
        return 0
    fi
}

# Verifica uso do Docker
check_docker_usage() {
    if [ -d "/var/lib/docker" ]; then
        local docker_size=$(du -sh /var/lib/docker 2>/dev/null | cut -f1)
        log "Docker (/var/lib/docker): $docker_size"
        
        # Conta imagens e containers
        if command -v docker &> /dev/null; then
            local images=$(docker images -q | wc -l)
            local containers=$(docker ps -a -q | wc -l)
            local volumes=$(docker volume ls -q | wc -l)
            
            log "Docker - Imagens: $images, Containers: $containers, Volumes: $volumes"
            
            # Alerta se tiver muito lixo
            if [ "$images" -gt 20 ]; then
                echo -e "${YELLOW}⚠️  Muitas imagens Docker ($images). Considere fazer prune.${NC}"
                log "SUGESTÃO: docker system prune -af --volumes"
            fi
        fi
    fi
}

# Verifica partições LVM
check_lvm_partitions() {
    if command -v lvs &> /dev/null; then
        log "Partições LVM:"
        lvs 2>/dev/null | tee -a "$LOG_FILE"
    fi
}

# Sugere limpeza
suggest_cleanup() {
    log "Sugestões de limpeza:"
    
    echo -e "\n${YELLOW}Comandos úteis para liberar espaço:${NC}"
    echo "1. Docker prune:"
    echo "   docker system prune -af --volumes"
    echo ""
    echo "2. Logs antigos:"
    echo "   journalctl --vacuum-time=7d"
    echo "   find /var/log -type f -name '*.log' -mtime +30 -delete"
    echo ""
    echo "3. Cache de apt:"
    echo "   apt-get clean && apt-get autoclean"
    echo ""
    echo "4. Temporários:"
    echo "   rm -rf /tmp/* /var/tmp/*"
    echo ""
}

# Main
main() {
    log "========================================="
    log "Iniciando verificação de disco (threshold: ${THRESHOLD}%)"
    
    check_root_partition
    local root_status=$?
    
    check_docker_usage
    check_lvm_partitions
    
    if [ $root_status -ne 0 ]; then
        suggest_cleanup
        exit 1
    fi
    
    log "Verificação concluída com sucesso"
    log "========================================="
    exit 0
}

main "$@"
