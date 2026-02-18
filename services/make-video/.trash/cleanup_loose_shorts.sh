#!/bin/bash
# Script para limpar vídeos shorts soltos (sem amarração com job_id)
# Esses arquivos são de jobs antigos e não podem ser processados

set -e

SHORTS_DIR="/root/YTCaption-Easy-Youtube-API/services/make-video/data/raw/shorts"

echo "🧹 Limpeza de Shorts Soltos"
echo "============================"
echo ""

cd "$SHORTS_DIR" || exit 1

# Contar arquivos soltos (mp4 direto na raiz)
LOOSE_FILES=$(find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) 2>/dev/null | wc -l)

if [ "$LOOSE_FILES" -eq 0 ]; then
    echo "✅ Nenhum arquivo solto encontrado!"
    echo ""
    exit 0
fi

echo "⚠️  Encontrados $LOOSE_FILES arquivos soltos (sem job_id)"
echo ""

# Listar arquivos
echo "📋 Arquivos que serão removidos:"
find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) 2>/dev/null | head -20
if [ "$LOOSE_FILES" -gt 20 ]; then
    echo "   ... e mais $(($LOOSE_FILES - 20)) arquivos"
fi
echo ""

# Calcular tamanho
TOTAL_SIZE=$(find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) -exec du -ch {} + 2>/dev/null | grep total | cut -f1)
echo "💾 Espaço a ser liberado: $TOTAL_SIZE"
echo ""

# Confirmação
read -p "🗑️  Deseja remover esses arquivos? (sim/não): " CONFIRM

if [ "$CONFIRM" != "sim" ]; then
    echo "❌ Operação cancelada."
    exit 0
fi

echo ""
echo "🗑️  Removendo arquivos soltos..."

# Remover arquivos
REMOVED=0
find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) 2>/dev/null | while read file; do
    if rm "$file" 2>/dev/null; then
        REMOVED=$((REMOVED + 1))
        echo "   ✓ $(basename "$file")"
    fi
done

echo ""
echo "✅ Limpeza concluída!"
echo ""

# Verificar estrutura restante
echo "📁 Estrutura atual (jobs com pastas):"
find . -maxdepth 1 -type d ! -name "." | head -10

REMAINING=$(find . -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.webm" -o -name "*.mkv" \) 2>/dev/null | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo ""
    echo "✅ Todos os arquivos soltos foram removidos!"
else
    echo ""
    echo "⚠️  Ainda restam $REMAINING arquivos soltos"
fi

echo ""
echo "📊 Espaço em data/raw/shorts/:"
du -sh "$SHORTS_DIR"
