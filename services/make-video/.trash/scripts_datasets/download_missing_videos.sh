#!/bin/bash

# Script para baixar os vídeos faltantes após o acidente de deleção
# Gerado automaticamente - 2025-02-14

set -e

echo "🔽 Baixando vídeos faltantes..."
echo ""

# Criar diretórios se não existirem
mkdir -p storage/validation/sample_OK
mkdir -p storage/validation/sample_NOT_OK

cd "$(dirname "$0")/.."

# Verificar se yt-dlp está instalado
if ! command -v yt-dlp &> /dev/null; then
    echo "❌ yt-dlp não encontrado. Instalando..."
    pip install yt-dlp
fi

# =====================================================
# sample_OK (SEM legendas) - 6 vídeos faltando
# =====================================================
echo "📁 Baixando sample_OK (SEM legendas)..."
echo ""

VIDEOS_OK=(
    "IyZ-sdLQATM"
    "KWC32RL-wgc"
    "XGrMrVFuc-E"
    "bH1hczbzm9U"
    "fRf_Uh39hVQ"
    "kVTr1c9IL8w"
)

for video_id in "${VIDEOS_OK[@]}"; do
    output_file="storage/validation/sample_OK/${video_id}.mp4"
    
    if [ -f "$output_file" ]; then
        echo "  ⏭️  ${video_id}.mp4 já existe"
        continue
    fi
    
    echo "  🔽 Baixando ${video_id}..."
    
    yt-dlp "https://youtube.com/watch?v=${video_id}" \
        -o "$output_file" \
        --no-playlist \
        --quiet \
        --no-warnings || {
        echo "  ⚠️  Erro ao baixar ${video_id}, tentando com shorts..."
        yt-dlp "https://youtube.com/shorts/${video_id}" \
            -o "$output_file" \
            --no-playlist \
            --quiet \
            --no-warnings || echo "  ❌ Falha ao baixar ${video_id}"
    }
    
    if [ -f "$output_file" ]; then
        size=$(du -h "$output_file" | cut -f1)
        echo "  ✅ ${video_id}.mp4 (${size})"
    fi
done

echo ""

# =====================================================
# sample_NOT_OK (COM legendas) - 14 vídeos faltando
# =====================================================
echo "📁 Baixando sample_NOT_OK (COM legendas)..."
echo ""

VIDEOS_NOT_OK=(
    "IQDr_KnwTCI"
    "J38GgWyenfc"
    "Kqbgaom-Ox8"
    "RgKo_-fabR8"
    "TR_YdL6D30k"
    "a-c9gMlZbTc"
    "a-hsqkOn2TE"
    "dxoZArrE_EY"
    "f2wrmVP7l0M"
    "f7jY8kuPCSU"
    "hX369irKPgY"
    "uZH0yp3k2ug"
    "video_3AdZJp7eBFHDAQqggaX2Wv"
    "vqUYNpxb6qA"
)

for video_id in "${VIDEOS_NOT_OK[@]}"; do
    # Baixar versão normal
    output_file="storage/validation/sample_NOT_OK/${video_id}.mp4"
    output_file_h264="storage/validation/sample_NOT_OK/${video_id}_h264.mp4"
    
    if [ -f "$output_file" ] && [ -f "$output_file_h264" ]; then
        echo "  ⏭️  ${video_id} já existe (ambas versões)"
        continue
    fi
    
    echo "  🔽 Baixando ${video_id}..."
    
    # Se é "video_3..." é um ID especial do sistema, pular
    if [[ "$video_id" == video_* ]]; then
        echo "  ⚠️  ${video_id} é ID interno, não é do YouTube"
        continue
    fi
    
    # Tentar baixar
    yt-dlp "https://youtube.com/watch?v=${video_id}" \
        -o "$output_file" \
        --no-playlist \
        --quiet \
        --no-warnings || {
        echo "  ⚠️  Erro ao baixar ${video_id}, tentando com shorts..."
        yt-dlp "https://youtube.com/shorts/${video_id}" \
            -o "$output_file" \
            --no-playlist \
            --quiet \
            --no-warnings || echo "  ❌ Falha ao baixar ${video_id}"
    }
    
    if [ -f "$output_file" ]; then
        size=$(du -h "$output_file" | cut -f1)
        echo "  ✅ ${video_id}.mp4 (${size})"
        
        # Copiar como versão _h264 também
        cp "$output_file" "$output_file_h264"
        echo "  ✅ ${video_id}_h264.mp4 (cópia)"
    fi
done

echo ""
echo "============================================================"
echo "✅ Download concluído!"
echo ""
echo "📊 Verificando status final..."

python3 << 'PYTHON_EOF'
import json
import os

with open('storage/validation/sample_OK/ground_truth.json') as f:
    sample_ok = json.load(f)

with open('storage/validation/sample_NOT_OK/ground_truth.json') as f:
    sample_not_ok = json.load(f)

recovered_ok = sum(1 for v in sample_ok['videos'] if os.path.exists(f"storage/validation/sample_OK/{v['filename']}"))
recovered_not_ok = sum(1 for v in sample_not_ok['videos'] if os.path.exists(f"storage/validation/sample_NOT_OK/{v['filename']}"))

total_ok = len(sample_ok['videos'])
total_not_ok = len(sample_not_ok['videos'])

print(f"sample_OK: {recovered_ok}/{total_ok} ({recovered_ok/total_ok*100:.1f}%)")
print(f"sample_NOT_OK: {recovered_not_ok}/{total_not_ok} ({recovered_not_ok/total_not_ok*100:.1f}%)")
print(f"TOTAL: {recovered_ok + recovered_not_ok}/{total_ok + total_not_ok} ({(recovered_ok + recovered_not_ok)/(total_ok + total_not_ok)*100:.1f}%)")
PYTHON_EOF

echo ""
