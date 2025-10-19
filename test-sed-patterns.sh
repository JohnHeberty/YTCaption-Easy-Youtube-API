#!/bin/bash

################################################################################
# TEST SCRIPT: Validate docker-compose.yml sed patterns
# Este script testa os padrões de substituição do start.sh
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

echo "Testing docker-compose.yml sed patterns..."
echo ""

# Backup original
cp docker-compose.yml docker-compose.yml.test-backup

# Test values
DOCKER_CPUS=4
DOCKER_CPUS_RESERVATION=2
DOCKER_MEMORY="8G"
DOCKER_MEMORY_RESERVATION="4G"
WHISPER_MODEL="base"
DISABLE_PARALLEL=true
PARALLEL_WORKERS=2

print_info "Test 1: Update CPU limits (4 cores)"
sed -i "s/cpus: '[0-9.]*'/cpus: '$DOCKER_CPUS.0'/" docker-compose.yml
grep "cpus:" docker-compose.yml | head -1

print_info "Test 2: Update memory limits (8G)"
sed -i "s/memory: [0-9]*G/memory: $DOCKER_MEMORY/" docker-compose.yml
grep "memory:" docker-compose.yml | head -1

print_info "Test 3: Update CPU reservations (2 cores)"
sed -i "/reservations:/,/memory:/ s/cpus: '[0-9.]*'/cpus: '$DOCKER_CPUS_RESERVATION.0'/" docker-compose.yml
grep "cpus:" docker-compose.yml | tail -1

print_info "Test 4: Update memory reservations (4G)"
sed -i "/reservations:/,/memory:/ s/memory: [0-9]*G/memory: $DOCKER_MEMORY_RESERVATION/" docker-compose.yml
grep "memory:" docker-compose.yml | tail -1

print_info "Test 5: Update WHISPER_MODEL"
sed -i "s/WHISPER_MODEL=.*/WHISPER_MODEL=$WHISPER_MODEL/" docker-compose.yml
grep "WHISPER_MODEL=" docker-compose.yml

print_info "Test 6: Disable PARALLEL TRANSCRIPTION"
sed -i "s/ENABLE_PARALLEL_TRANSCRIPTION=.*/ENABLE_PARALLEL_TRANSCRIPTION=false/" docker-compose.yml
grep "ENABLE_PARALLEL_TRANSCRIPTION=" docker-compose.yml

print_info "Test 7: Update PARALLEL_WORKERS"
sed -i "s/PARALLEL_WORKERS=.*/PARALLEL_WORKERS=2/" docker-compose.yml
grep "PARALLEL_WORKERS=" docker-compose.yml

echo ""
echo "========================================"
echo "RESULTS:"
echo "========================================"
echo ""
echo "Environment variables section:"
grep -A 15 "environment:" docker-compose.yml | grep -E "(WHISPER_MODEL|ENABLE_PARALLEL|PARALLEL_WORKERS)"

echo ""
echo "Resources section:"
grep -A 10 "resources:" docker-compose.yml | grep -E "(cpus|memory)"

echo ""
echo "========================================"
print_info "Restoring original docker-compose.yml..."
mv docker-compose.yml.test-backup docker-compose.yml
print_success "Test complete!"
