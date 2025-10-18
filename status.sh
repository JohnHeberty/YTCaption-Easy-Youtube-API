#!/bin/bash

################################################################################
# YTCaption - Status and Logs Script
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Detect compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "Docker Compose not found!"
    exit 1
fi

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}  YTCaption Status${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Show container status
$COMPOSE_CMD ps

echo ""
echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}  Recent Logs (last 50 lines)${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Show recent logs
$COMPOSE_CMD logs --tail=50

echo ""
echo -e "${GREEN}TIP: Use '$COMPOSE_CMD logs -f' to follow logs in real-time${NC}"
