#!/bin/bash
set -e

# Configurar bibliotecas CUDA compat para compatibilidade com driver
export LD_LIBRARY_PATH="/usr/local/cuda-12.4/compat:${LD_LIBRARY_PATH}"
export CUDA_HOME="/usr/local/cuda-12.4"

# Executar comando
exec "$@"
