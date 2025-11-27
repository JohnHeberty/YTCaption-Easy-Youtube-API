#!/bin/bash
# validate-deps.sh - Script de validação de dependências RVC
# Sprint 2: Dependencies

set -e

echo "=================================================="
echo "  RVC Dependencies Validation - Sprint 2"
echo "  Audio Voice Service"
echo "=================================================="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

CHECKS_PASSED=0
CHECKS_FAILED=0

# Python deve estar disponível
if ! command -v python &> /dev/null; then
    print_error "Python not found"
    exit 1
fi

echo "1. Checking tts-with-rvc..."
if python -c "import tts_with_rvc; print(f'Version: {tts_with_rvc.__version__}')" 2>/dev/null; then
    print_success "tts-with-rvc installed"
    ((CHECKS_PASSED++))
else
    print_error "tts-with-rvc not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "2. Checking fairseq..."
if python -c "import fairseq; print(f'Version: {fairseq.__version__}')" 2>/dev/null; then
    print_success "fairseq installed"
    ((CHECKS_PASSED++))
else
    print_error "fairseq not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "3. Checking faiss..."
if python -c "import faiss; print('FAISS OK')" 2>/dev/null; then
    print_success "faiss installed"
    ((CHECKS_PASSED++))
else
    print_error "faiss not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "4. Checking librosa..."
if python -c "import librosa; print(f'Version: {librosa.__version__}')" 2>/dev/null; then
    print_success "librosa installed"
    ((CHECKS_PASSED++))
else
    print_error "librosa not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "5. Checking parselmouth..."
if python -c "import parselmouth; print('Parselmouth OK')" 2>/dev/null; then
    print_success "parselmouth installed"
    ((CHECKS_PASSED++))
else
    print_error "parselmouth not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "6. Checking torchcrepe..."
if python -c "import torchcrepe; print('Torchcrepe OK')" 2>/dev/null; then
    print_success "torchcrepe installed"
    ((CHECKS_PASSED++))
else
    print_error "torchcrepe not installed"
    ((CHECKS_FAILED++))
fi
echo ""

echo "7. Checking RVC module structure..."
if python -c "from tts_with_rvc.infer.vc.modules import VC; print('VC OK')" 2>/dev/null; then
    print_success "VC class available"
    ((CHECKS_PASSED++))
else
    print_error "VC class not found"
    ((CHECKS_FAILED++))
fi
echo ""

echo "8. Checking XTTS compatibility..."
if python -c "from TTS.api import TTS; print('XTTS OK')" 2>/dev/null; then
    print_success "XTTS still works (no regression)"
    ((CHECKS_PASSED++))
else
    print_error "XTTS broken (regression detected)"
    ((CHECKS_FAILED++))
fi
echo ""

# Resumo
echo "=================================================="
echo "  Validation Summary"
echo "=================================================="
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
if [ $CHECKS_FAILED -gt 0 ]; then
    echo -e "Checks failed: ${RED}$CHECKS_FAILED${NC}"
    echo ""
    print_error "RVC dependencies NOT ready"
    exit 1
else
    echo -e "Checks failed: ${GREEN}0${NC}"
    echo ""
    print_success "All RVC dependencies installed! ✓"
    echo ""
    print_info "Next steps:"
    echo "  1. Run tests: pytest tests/test_rvc_dependencies.py -v"
    echo "  2. Check health: python -c 'from app.rvc_dependencies import rvc_deps; print(rvc_deps.check_all())'"
    exit 0
fi
