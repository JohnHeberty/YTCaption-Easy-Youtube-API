#!/bin/bash
# Script de auditoria contínua de arquivos soltos
# Verifica todas as pastas do make-video para garantir organização

set -e

BASE_DIR="/root/YTCaption-Easy-Youtube-API/services/make-video"
cd "$BASE_DIR"

echo "🔍 AUDITORIA DE ARQUIVOS SOLTOS"
echo "================================"
echo ""

TOTAL_LOOSE=0

# Função para verificar pasta
check_folder() {
    local folder=$1
    local name=$2
    
    if [ ! -d "$folder" ]; then
        echo "⚠️  Pasta não existe: $folder"
        return
    fi
    
    # Contar arquivos soltos (vídeos/áudios na raiz)
    local loose_count=$(find "$folder" -maxdepth 1 -type f \( \
        -name "*.mp4" -o \
        -name "*.mp3" -o \
        -name "*.wav" -o \
        -name "*.m4a" -o \
        -name "*.webm" -o \
        -name "*.mkv" \
    \) 2>/dev/null | wc -l)
    
    if [ "$loose_count" -eq 0 ]; then
        echo "✅ $name: 0 arquivos soltos"
    else
        echo "❌ $name: $loose_count arquivos SOLTOS!"
        TOTAL_LOOSE=$((TOTAL_LOOSE + loose_count))
        
        # Listar até 5 arquivos
        echo "   Exemplos:"
        find "$folder" -maxdepth 1 -type f \( \
            -name "*.mp4" -o -name "*.mp3" -o -name "*.wav" -o \
            -name "*.m4a" -o -name "*.webm" -o -name "*.mkv" \
        \) 2>/dev/null | head -5 | while read file; do
            echo "     - $(basename "$file")"
        done
    fi
}

# Verificar pastas principais
echo "📁 data/raw/shorts (vídeos shorts baixados):"
check_folder "data/raw/shorts" "Shorts"
echo ""

echo "📁 data/raw/audio (áudios de entrada):"
check_folder "data/raw/audio" "Áudios"
echo ""

echo "📁 data/transform/temp (arquivos temporários):"
check_folder "data/transform/temp" "Temp"
echo ""

echo "📁 data/approved/output (vídeos finais):"
check_folder "data/approved/output" "Output"
echo ""

# Resumo
echo "================================"
if [ "$TOTAL_LOOSE" -eq 0 ]; then
    echo "✅ AUDITORIA OK: Nenhum arquivo solto!"
    echo ""
    echo "📊 Estrutura correta:"
    echo "   - Shorts organizados em: data/raw/shorts/{job_id}/"
    echo "   - Áudios organizados em: data/raw/audio/{job_id}/"
    echo "   - Temp organizados em: data/transform/temp/{job_id}/"
    echo "   - Outputs nomeados com: {job_id}_final.mp4"
    exit 0
else
    echo "❌ PROBLEMAS ENCONTRADOS: $TOTAL_LOOSE arquivos soltos!"
    echo ""
    echo "💡 Para corrigir, execute:"
    echo "   ./cleanup_loose_shorts.sh    # Limpar shorts"
    echo "   # (criar scripts similares para outras pastas)"
    exit 1
fi
