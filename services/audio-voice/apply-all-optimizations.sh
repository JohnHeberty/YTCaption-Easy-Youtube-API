#!/bin/bash
################################################################################
# apply-all-optimizations.sh - Aplica TODAS as otimizações automaticamente
#
# Este script:
# 1. Faz backup dos arquivos atuais
# 2. Aplica Dockerfile otimizado
# 3. Aplica .dockerignore otimizado
# 4. Configura monitoramento
# 5. Configura limpeza automática
# 6. Valida mudanças
#
# Uso: ./apply-all-optimizations.sh [--dry-run]
#   --dry-run: Mostra o que seria feito sem aplicar mudanças
################################################################################

set -e

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Funções
info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }
step() { echo -e "\n${CYAN}▶${NC} $1\n"; }

# Header
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        APLICAÇÃO AUTOMÁTICA DE OTIMIZAÇÕES DE DISCO              ║
║                  Audio Voice Service v3.0.0                      ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF

if $DRY_RUN; then
    warning "MODO DRY-RUN: Apenas mostrando o que seria feito"
fi

echo ""
info "Início: $(date)"
echo ""

################################################################################
# FASE 1: PRÉ-VALIDAÇÃO
################################################################################
step "[FASE 1/6] PRÉ-VALIDAÇÃO"

# Verifica se estamos no diretório correto
if [ ! -f "Dockerfile" ] || [ ! -f "requirements.txt" ]; then
    error "Este script deve ser executado no diretório services/audio-voice"
    exit 1
fi
success "Diretório correto"

# Verifica espaço em disco
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
DISK_AVAIL=$(df -h / | tail -1 | awk '{print $4}')

info "Espaço em disco: ${DISK_USAGE}% usado, ${DISK_AVAIL} disponível"

if [ "$DISK_USAGE" -gt 70 ]; then
    warning "Espaço em disco baixo. Considere limpar antes de continuar."
    read -p "Deseja executar 'docker system prune -af' agora? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] && [ "$DRY_RUN" == "false" ]; then
        docker system prune -af
        success "Docker cache limpo"
    fi
fi

# Verifica se arquivos otimizados existem
if [ ! -f "Dockerfile.optimized" ]; then
    error "Dockerfile.optimized não encontrado!"
    exit 1
fi
success "Arquivos de otimização encontrados"

################################################################################
# FASE 2: BACKUP
################################################################################
step "[FASE 2/6] BACKUP DE ARQUIVOS ATUAIS"

BACKUP_DIR="backup-$(date +%Y%m%d-%H%M%S)"

if [ "$DRY_RUN" == "false" ]; then
    mkdir -p "$BACKUP_DIR"
    
    # Backup Dockerfile
    if [ -f "Dockerfile" ]; then
        cp Dockerfile "$BACKUP_DIR/"
        success "Backup: Dockerfile → $BACKUP_DIR/Dockerfile"
    fi
    
    # Backup .dockerignore
    if [ -f ".dockerignore" ]; then
        cp .dockerignore "$BACKUP_DIR/"
        success "Backup: .dockerignore → $BACKUP_DIR/.dockerignore"
    fi
    
    # Backup docker-compose.yml (se existir)
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "$BACKUP_DIR/"
        success "Backup: docker-compose.yml → $BACKUP_DIR/docker-compose.yml"
    fi
    
    info "Backups salvos em: $BACKUP_DIR"
else
    info "Criaria backup em: $BACKUP_DIR"
fi

################################################################################
# FASE 3: APLICAR OTIMIZAÇÕES DE DOCKERFILE
################################################################################
step "[FASE 3/6] APLICAR OTIMIZAÇÕES"

# 3.1 Dockerfile
if [ "$DRY_RUN" == "false" ]; then
    cp Dockerfile.optimized Dockerfile
    success "Dockerfile otimizado aplicado"
else
    info "Aplicaria: Dockerfile.optimized → Dockerfile"
fi

# 3.2 .dockerignore
if [ "$DRY_RUN" == "false" ]; then
    cp .dockerignore.optimized .dockerignore
    success ".dockerignore otimizado aplicado"
else
    info "Aplicaria: .dockerignore.optimized → .dockerignore"
fi

# 3.3 Verifica mudanças
echo ""
info "Resumo de mudanças:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$BACKUP_DIR/Dockerfile" ]; then
    DOCKERFILE_LINES_BEFORE=$(wc -l < "$BACKUP_DIR/Dockerfile")
    DOCKERFILE_LINES_AFTER=$(wc -l < "Dockerfile")
    info "Dockerfile: $DOCKERFILE_LINES_BEFORE → $DOCKERFILE_LINES_AFTER linhas"
fi

if [ -f "$BACKUP_DIR/.dockerignore" ]; then
    DOCKERIGNORE_LINES_BEFORE=$(wc -l < "$BACKUP_DIR/.dockerignore")
    DOCKERIGNORE_LINES_AFTER=$(wc -l < ".dockerignore")
    info ".dockerignore: $DOCKERIGNORE_LINES_BEFORE → $DOCKERIGNORE_LINES_AFTER linhas"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

################################################################################
# FASE 4: CONFIGURAR MONITORAMENTO
################################################################################
step "[FASE 4/6] CONFIGURAR MONITORAMENTO DE DISCO"

# Copia script de monitoramento
if [ -f "scripts/check-disk.sh" ]; then
    if [ "$DRY_RUN" == "false" ]; then
        sudo cp scripts/check-disk.sh /usr/local/bin/
        sudo chmod +x /usr/local/bin/check-disk.sh
        success "Script de monitoramento instalado: /usr/local/bin/check-disk.sh"
    else
        info "Instalaria: scripts/check-disk.sh → /usr/local/bin/"
    fi
    
    # Configura cron
    CRON_LINE="*/15 * * * * /usr/local/bin/check-disk.sh 80"
    
    if [ "$DRY_RUN" == "false" ]; then
        # Verifica se cron já existe
        if ! crontab -l 2>/dev/null | grep -q "check-disk.sh"; then
            (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
            success "Cron de monitoramento configurado (a cada 15 minutos)"
        else
            info "Cron de monitoramento já configurado"
        fi
    else
        info "Configuraria cron: $CRON_LINE"
    fi
else
    warning "scripts/check-disk.sh não encontrado, pulando monitoramento"
fi

################################################################################
# FASE 5: CONFIGURAR LIMPEZA AUTOMÁTICA
################################################################################
step "[FASE 5/6] CONFIGURAR LIMPEZA AUTOMÁTICA DO DOCKER"

PRUNE_CRON="0 3 * * * docker system prune -af --volumes --filter 'until=48h'"

if [ "$DRY_RUN" == "false" ]; then
    if ! crontab -l 2>/dev/null | grep -q "docker system prune"; then
        (crontab -l 2>/dev/null; echo "$PRUNE_CRON") | crontab -
        success "Cron de limpeza Docker configurado (diário às 3h)"
    else
        info "Cron de limpeza Docker já configurado"
    fi
else
    info "Configuraria cron: $PRUNE_CRON"
fi

################################################################################
# FASE 6: VALIDAÇÃO PÓS-APLICAÇÃO
################################################################################
step "[FASE 6/6] VALIDAÇÃO"

if [ "$DRY_RUN" == "false" ]; then
    # Valida Dockerfile
    if grep -q "FROM.*AS builder" Dockerfile && grep -q "FROM.*AS runtime" Dockerfile; then
        success "Dockerfile: Multi-stage build ✓"
    else
        error "Dockerfile: Multi-stage build NÃO detectado"
    fi
    
    # Valida .dockerignore
    REQUIRED=("tests/" "docs/" "sprints_")
    MISSING=()
    for req in "${REQUIRED[@]}"; do
        if ! grep -q "$req" .dockerignore; then
            MISSING+=("$req")
        fi
    done
    
    if [ ${#MISSING[@]} -eq 0 ]; then
        success ".dockerignore: Todas as exclusões críticas presentes ✓"
    else
        warning ".dockerignore: Faltam exclusões: ${MISSING[*]}"
    fi
    
    # Verifica crons
    if crontab -l 2>/dev/null | grep -q "check-disk.sh"; then
        success "Monitoramento: Cron configurado ✓"
    fi
    
    if crontab -l 2>/dev/null | grep -q "docker system prune"; then
        success "Limpeza automática: Cron configurado ✓"
    fi
fi

################################################################################
# RESUMO FINAL
################################################################################
echo ""
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════╗
║                         RESUMO FINAL                              ║
╚═══════════════════════════════════════════════════════════════════╝
EOF

echo ""
success "✅ Otimizações aplicadas com sucesso!"
echo ""

if [ "$DRY_RUN" == "false" ]; then
    info "Arquivos modificados:"
    echo "  • Dockerfile (backup em $BACKUP_DIR/)"
    echo "  • .dockerignore (backup em $BACKUP_DIR/)"
    echo ""
    info "Configurações ativadas:"
    echo "  • Monitoramento de disco (a cada 15 min)"
    echo "  • Limpeza automática Docker (diário às 3h)"
    echo ""
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    warning "PRÓXIMOS PASSOS:"
    echo ""
    echo "1️⃣  Validar mudanças:"
    echo "   ./scripts/validate-optimization.sh pre"
    echo ""
    echo "2️⃣  Build da nova imagem:"
    echo "   export DOCKER_BUILDKIT=1"
    echo "   docker build --target runtime -t audio-voice:3.0.0 ."
    echo ""
    echo "3️⃣  Validar build:"
    echo "   ./scripts/validate-optimization.sh post"
    echo ""
    echo "4️⃣  Atualizar docker-compose.yml:"
    echo "   • Adicionar volumes persistentes para modelos"
    echo "   • Ver APPLY_OPTIMIZATION.md seção 4.1"
    echo ""
    echo "5️⃣  Deploy:"
    echo "   docker-compose up -d"
    echo "   docker-compose exec audio-voice python scripts/download_models.py"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    info "📚 Documentação completa em:"
    echo "   • README_OPTIMIZATION.md (visão geral)"
    echo "   • APPLY_OPTIMIZATION.md (guia detalhado)"
    echo "   • INFRASTRUCTURE_SETUP.md (infra avançada)"
    echo ""
    info "🔄 Para reverter mudanças:"
    echo "   cp $BACKUP_DIR/Dockerfile Dockerfile"
    echo "   cp $BACKUP_DIR/.dockerignore .dockerignore"
    echo ""
else
    info "Este foi um DRY-RUN. Nenhuma mudança foi aplicada."
    echo ""
    info "Para aplicar as mudanças, execute:"
    echo "   ./apply-all-optimizations.sh"
    echo ""
fi

info "Término: $(date)"
echo ""

################################################################################
# CHECKLIST FINAL
################################################################################
if [ "$DRY_RUN" == "false" ]; then
    cat << EOF
┌─────────────────────────────────────────────────────────────────┐
│                      CHECKLIST PÓS-APLICAÇÃO                    │
├─────────────────────────────────────────────────────────────────┤
│ [ ] Validar mudanças (validate-optimization.sh pre)             │
│ [ ] Build da nova imagem                                        │
│ [ ] Validar build (validate-optimization.sh post)               │
│ [ ] Atualizar docker-compose.yml com volumes                    │
│ [ ] Testar em staging                                           │
│ [ ] Deploy em produção                                          │
│ [ ] Monitorar uso de disco por 24h                              │
│ [ ] Verificar alertas funcionando                               │
└─────────────────────────────────────────────────────────────────┘
EOF
fi

echo ""
success "Script concluído com sucesso!"
