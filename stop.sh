#!/bin/bash

################################################################################
# YTCaption - Stop Script
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Detect compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    print_error "Docker Compose not found!"
    exit 1
fi

print_info "Stopping YTCaption..."

$COMPOSE_CMD down

if [ $? -eq 0 ]; then
    print_success "YTCaption stopped successfully!"
else
    print_error "Failed to stop YTCaption"
    exit 1
fi
