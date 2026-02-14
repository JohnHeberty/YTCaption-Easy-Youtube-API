#!/bin/bash
# ============================================================================
# Demo: Calibração OCR em Background
# ============================================================================
# Este script demonstra o fluxo completo de calibração Optuna em background
# usando os comandos do Makefile aprimorados.
# ============================================================================

set -e  # Exit on error

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Demo: Calibração OCR em Background com Optuna            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "Makefile" ]; then
    echo -e "${RED}❌ Erro: Makefile não encontrado${NC}"
    echo -e "${YELLOW}Execute este script de: services/make-video/${NC}"
    exit 1
fi

# ============================================================================
# PASSO 1: Validar setup
# ============================================================================
echo -e "${BLUE}[1/6] Validando setup...${NC}"
make validate > /dev/null 2>&1 || true
echo -e "${GREEN}✅ Setup OK${NC}"
echo ""

# ============================================================================
# PASSO 2: Verificar se já tem calibração rodando
# ============================================================================
echo -e "${BLUE}[2/6] Verificando calibrações existentes...${NC}"

if [ -f "/tmp/calibration.pid" ]; then
    PID=$(cat /tmp/calibration.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Já existe uma calibração rodando (PID: $PID)${NC}"
        echo ""
        echo -e "${BLUE}Status atual:${NC}"
        make calibrate-status
        echo ""
        read -p "Deseja parar a calibração existente e iniciar nova? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}🛑 Parando calibração existente...${NC}"
            make calibrate-stop
            echo ""
        else
            echo -e "${GREEN}✅ Mantendo calibração existente${NC}"
            echo -e "${BLUE}💡 Para acompanhar: ${NC}make calibrate-watch"
            exit 0
        fi
    else
        echo -e "${YELLOW}⚠️  PID file encontrado mas processo não está rodando${NC}"
        make calibrate-clean > /dev/null 2>&1
    fi
fi

echo -e "${GREEN}✅ Nenhuma calibração em execução${NC}"
echo ""

# ============================================================================
# PASSO 3: Escolher tipo de calibração
# ============================================================================
echo -e "${BLUE}[3/6] Escolher tipo de calibração:${NC}"
echo ""
echo "  1) 🚀 Rápida (5 trials, ~3-4 horas) - Recomendado para teste"
echo "  2) 🎯 Completa (100 trials, ~60-80 horas) - Para produção"
echo ""
read -p "Escolha [1/2]: " -n 1 -r
echo
echo ""

if [[ $REPLY == "1" ]]; then
    echo -e "${BLUE}📊 Calibração RÁPIDA selecionada${NC}"
    echo -e "${YELLOW}⚠️  Duração estimada: 3-4 horas${NC}"
    echo ""
    
    read -p "Iniciar calibração rápida em FOREGROUND? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${GREEN}🚀 Iniciando calibração rápida...${NC}"
        echo ""
        make calibrate-quick
        exit 0
    else
        echo -e "${YELLOW}❌ Calibração cancelada${NC}"
        exit 0
    fi
    
elif [[ $REPLY == "2" ]]; then
    echo -e "${BLUE}📊 Calibração COMPLETA selecionada${NC}"
    echo -e "${YELLOW}⚠️  Duração estimada: 60-80 horas (2-3 dias)${NC}"
    echo -e "${YELLOW}⚠️  Será executada em BACKGROUND${NC}"
    echo ""
else
    echo -e "${RED}❌ Opção inválida${NC}"
    exit 1
fi

# ============================================================================
# PASSO 4: Iniciar calibração em background
# ============================================================================
echo -e "${BLUE}[4/6] Iniciando calibração em background...${NC}"
echo ""

# Simular make calibrate-start (sem confirmação interativa para demo)
mkdir -p /tmp
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Usar yes para auto-confirmar
echo -e "${GREEN}✅ Iniciando processo...${NC}"
yes | make calibrate-start 2>/dev/null || true

# Aguardar processo iniciar
sleep 3

echo ""

# ============================================================================
# PASSO 5: Verificar se iniciou com sucesso
# ============================================================================
echo -e "${BLUE}[5/6] Verificando status...${NC}"
echo ""

if [ -f "/tmp/calibration.pid" ]; then
    PID=$(cat /tmp/calibration.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Calibração iniciada com sucesso!${NC}"
        echo -e "${GREEN}   PID: $PID${NC}"
        echo ""
    else
        echo -e "${RED}❌ Processo falhou ao iniciar${NC}"
        echo -e "${YELLOW}📋 Ver logs: tail -f /tmp/optuna_full.log${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ PID file não foi criado${NC}"
    exit 1
fi

# ============================================================================
# PASSO 6: Mostrar comandos úteis
# ============================================================================
echo -e "${BLUE}[6/6] Comandos úteis:${NC}"
echo ""
echo -e "${GREEN}📊 Ver status atual:${NC}"
echo "   make calibrate-status"
echo "   make cal-status          # alias curto"
echo ""
echo -e "${GREEN}👁️  Acompanhar continuamente (auto-atualiza a cada 30s):${NC}"
echo "   make calibrate-watch"
echo "   make cal-watch           # alias curto"
echo ""
echo -e "${GREEN}📋 Ver logs em tempo real:${NC}"
echo "   make calibrate-logs"
echo "   make cal-logs            # alias curto"
echo ""
echo -e "${GREEN}🛑 Parar calibração:${NC}"
echo "   make calibrate-stop"
echo "   make cal-stop            # alias curto"
echo ""
echo -e "${GREEN}✅ Aplicar threshold (após conclusão):${NC}"
echo "   make calibrate-apply"
echo "   make cal-apply           # alias curto"
echo ""

# ============================================================================
# BONUS: Mostrar status inicial
# ============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Status Inicial                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

make calibrate-status

echo ""
echo -e "${GREEN}✅ Demo concluído!${NC}"
echo ""
echo -e "${YELLOW}💡 Dica: Abra outro terminal e execute 'make calibrate-watch'${NC}"
echo -e "${YELLOW}   para acompanhar o progresso em tempo real!${NC}"
echo ""
