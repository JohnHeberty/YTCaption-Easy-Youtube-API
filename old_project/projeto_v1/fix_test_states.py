#!/usr/bin/env python
"""Script para corrigir comparações de estado nos testes do CircuitBreaker."""

import re

# Ler arquivo
with open('tests/unit/infrastructure/test_circuit_breaker.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Substituições
replacements = [
    (r'\.state == "closed"', '.state == CircuitState.CLOSED'),
    (r'\.state == "open"', '.state == CircuitState.OPEN'),
    (r'\.state == "half_open"', '.state == CircuitState.HALF_OPEN'),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Salvar
with open('tests/unit/infrastructure/test_circuit_breaker.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Testes corrigidos! Substituídas todas as comparações de estado.")
