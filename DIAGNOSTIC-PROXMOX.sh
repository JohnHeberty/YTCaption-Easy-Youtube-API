#!/bin/bash

# ============================================
# 🔍 DIAGNÓSTICO COMPLETO - PROXMOX SERVER
# ============================================
# Este script verifica se o código no servidor
# está REALMENTE atualizado com as correções.
# ============================================

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        🔍 DIAGNÓSTICO COMPLETO - CÓDIGO PROXMOX           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# 1. GIT STATUS
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[1/6] GIT STATUS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}▶ Branch atual:${NC}"
git branch --show-current
echo ""

echo -e "${YELLOW}▶ Último commit local:${NC}"
git log --oneline -1
echo ""

echo -e "${YELLOW}▶ Últimos 7 commits (deve incluir 1fcdfa5 e 3e3d79c):${NC}"
git log --oneline -7
echo ""

echo -e "${YELLOW}▶ Verificando se commit 1fcdfa5 (CircuitBreaker fix) existe:${NC}"
if git log --oneline | grep -q "1fcdfa5"; then
    echo -e "${GREEN}✅ COMMIT 1fcdfa5 ENCONTRADO!${NC}"
else
    echo -e "${RED}❌ COMMIT 1fcdfa5 NÃO ENCONTRADO - CÓDIGO DESATUALIZADO!${NC}"
fi
echo ""

echo -e "${YELLOW}▶ Status do repositório:${NC}"
git status
echo ""

# ============================================
# 2. VERIFICAR CÓDIGO CircuitBreaker
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[2/6] CÓDIGO CircuitBreaker${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

CIRCUIT_FILE="src/infrastructure/utils/circuit_breaker.py"

echo -e "${YELLOW}▶ Verificando se acall() existe em circuit_breaker.py:${NC}"
if grep -q "async def acall" "$CIRCUIT_FILE"; then
    echo -e "${GREEN}✅ Método acall() ENCONTRADO!${NC}"
    echo ""
    echo -e "${YELLOW}▶ Código do método acall():${NC}"
    grep -A 15 "async def acall" "$CIRCUIT_FILE"
else
    echo -e "${RED}❌ Método acall() NÃO ENCONTRADO - CÓDIGO DESATUALIZADO!${NC}"
fi
echo ""

echo -e "${YELLOW}▶ Verificando se ainda existe call() síncrono (deve existir):${NC}"
if grep -q "def call(self, func" "$CIRCUIT_FILE"; then
    echo -e "${GREEN}✅ Método call() existe (backward compatibility)${NC}"
else
    echo -e "${YELLOW}⚠️  Método call() não encontrado (esperado se houver refactor)${NC}"
fi
echo ""

# ============================================
# 3. VERIFICAR CÓDIGO YouTubeDownloader
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[3/6] CÓDIGO YouTubeDownloader${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

DOWNLOADER_FILE="src/infrastructure/youtube/downloader.py"

echo -e "${YELLOW}▶ Verificando se downloader.py usa acall():${NC}"
if grep -q "acall" "$DOWNLOADER_FILE"; then
    echo -e "${GREEN}✅ acall() ENCONTRADO em downloader.py!${NC}"
    echo ""
    echo -e "${YELLOW}▶ Ocorrências de acall():${NC}"
    grep -n "acall" "$DOWNLOADER_FILE"
else
    echo -e "${RED}❌ acall() NÃO ENCONTRADO - downloader.py DESATUALIZADO!${NC}"
fi
echo ""

echo -e "${YELLOW}▶ Verificando se ainda existe .call() ANTIGO (NÃO DEVE EXISTIR):${NC}"
if grep -q "_circuit_breaker\.call(" "$DOWNLOADER_FILE"; then
    echo -e "${RED}❌ ERRO! Ainda usa .call() antigo:${NC}"
    grep -n "_circuit_breaker\.call(" "$DOWNLOADER_FILE"
else
    echo -e "${GREEN}✅ Não há .call() antigo (correto!)${NC}"
fi
echo ""

# ============================================
# 4. VERIFICAR DOCKER IMAGE
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[4/6] DOCKER IMAGE${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}▶ Data de criação da imagem Docker atual:${NC}"
docker images ytcaption-easy-youtube-api-whisper-transcription-api --format "{{.CreatedAt}}"
echo ""

echo -e "${YELLOW}▶ Verificando se há containers antigos (cache):${NC}"
docker ps -a --filter "name=whisper-transcription-api" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
echo ""

# ============================================
# 5. VERIFICAR CÓDIGO DENTRO DO CONTAINER
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[5/6] CÓDIGO DENTRO DO CONTAINER (CRÍTICO!)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

CONTAINER_NAME="whisper-transcription-api"

echo -e "${YELLOW}▶ Verificando se acall() existe DENTRO do container:${NC}"
if docker exec "$CONTAINER_NAME" grep -q "async def acall" "/app/src/infrastructure/utils/circuit_breaker.py" 2>/dev/null; then
    echo -e "${GREEN}✅ acall() EXISTE DENTRO DO CONTAINER!${NC}"
else
    echo -e "${RED}❌ acall() NÃO EXISTE DENTRO DO CONTAINER!${NC}"
    echo -e "${RED}   Isso significa que o build NÃO usou o código novo!${NC}"
fi
echo ""

echo -e "${YELLOW}▶ Verificando se downloader.py usa acall() DENTRO do container:${NC}"
if docker exec "$CONTAINER_NAME" grep -q "acall" "/app/src/infrastructure/youtube/downloader.py" 2>/dev/null; then
    echo -e "${GREEN}✅ downloader.py usa acall() DENTRO do container!${NC}"
    echo ""
    echo -e "${YELLOW}▶ Linhas com acall() dentro do container:${NC}"
    docker exec "$CONTAINER_NAME" grep -n "acall" "/app/src/infrastructure/youtube/downloader.py" 2>/dev/null
else
    echo -e "${RED}❌ downloader.py NÃO usa acall() dentro do container!${NC}"
fi
echo ""

echo -e "${YELLOW}▶ Verificando se downloader.py ainda usa .call() ANTIGO dentro do container:${NC}"
if docker exec "$CONTAINER_NAME" grep -q "_circuit_breaker\.call(" "/app/src/infrastructure/youtube/downloader.py" 2>/dev/null; then
    echo -e "${RED}❌ PROBLEMA CRÍTICO! Container ainda tem .call() antigo:${NC}"
    docker exec "$CONTAINER_NAME" grep -n "_circuit_breaker\.call(" "/app/src/infrastructure/youtube/downloader.py" 2>/dev/null
else
    echo -e "${GREEN}✅ Container NÃO usa .call() antigo (correto!)${NC}"
fi
echo ""

# ============================================
# 6. CHECKSUM DOS ARQUIVOS
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}[6/6] CHECKSUM (MD5) DOS ARQUIVOS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}▶ MD5 do circuit_breaker.py (host):${NC}"
md5sum "$CIRCUIT_FILE"
echo ""

echo -e "${YELLOW}▶ MD5 do circuit_breaker.py (container):${NC}"
docker exec "$CONTAINER_NAME" md5sum "/app/src/infrastructure/utils/circuit_breaker.py" 2>/dev/null || echo -e "${RED}Erro ao calcular MD5 do container${NC}"
echo ""

echo -e "${YELLOW}▶ MD5 do downloader.py (host):${NC}"
md5sum "$DOWNLOADER_FILE"
echo ""

echo -e "${YELLOW}▶ MD5 do downloader.py (container):${NC}"
docker exec "$CONTAINER_NAME" md5sum "/app/src/infrastructure/youtube/downloader.py" 2>/dev/null || echo -e "${RED}Erro ao calcular MD5 do container${NC}"
echo ""

# ============================================
# RESUMO FINAL
# ============================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}RESUMO DO DIAGNÓSTICO${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}Se os checksums (MD5) são DIFERENTES entre host e container,${NC}"
echo -e "${YELLOW}significa que o Docker build NÃO copiou o código novo!${NC}"
echo ""
echo -e "${YELLOW}Solução:${NC}"
echo -e "  1. ${GREEN}git pull origin main${NC}"
echo -e "  2. ${GREEN}docker-compose down${NC}"
echo -e "  3. ${GREEN}docker system prune -af --volumes${NC}  ${RED}(remove TUDO)${NC}"
echo -e "  4. ${GREEN}docker-compose build --no-cache --pull${NC}"
echo -e "  5. ${GREEN}docker-compose up -d${NC}"
echo ""
