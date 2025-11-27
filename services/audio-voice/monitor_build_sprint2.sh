#!/bin/bash
# Monitor do build Docker - Sprint 2.1
# Mostra progresso em tempo real

LOG_FILE="/tmp/docker-build-f5tts.log"

echo "========================================="
echo "Monitor de Build Docker - F5-TTS"
echo "========================================="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️  Log file não encontrado: $LOG_FILE"
    echo "Build ainda não iniciado ou log em outro local"
    exit 1
fi

# Função para extrair informações relevantes
show_progress() {
    echo "📊 Progresso atual:"
    echo ""
    
    # Step atual
    CURRENT_STEP=$(grep -oP '#\d+ \[\d+/\d+\]' "$LOG_FILE" | tail -1)
    if [ -n "$CURRENT_STEP" ]; then
        echo "   Step: $CURRENT_STEP"
    fi
    
    # Pacotes apt sendo instalados
    APT_INSTALLING=$(grep "Setting up" "$LOG_FILE" | tail -3)
    if [ -n "$APT_INSTALLING" ]; then
        echo ""
        echo "   Últimos pacotes APT:"
        echo "$APT_INSTALLING" | sed 's/^/      /'
    fi
    
    # Pip install
    PIP_INSTALLING=$(grep "Installing collected packages" "$LOG_FILE" | tail -1)
    if [ -n "$PIP_INSTALLING" ]; then
        echo ""
        echo "   $PIP_INSTALLING"
    fi
    
    # Git clone F5-TTS
    F5TTS_CLONE=$(grep -i "f5-tts" "$LOG_FILE" | tail -3)
    if [ -n "$F5TTS_CLONE" ]; then
        echo ""
        echo "   F5-TTS:"
        echo "$F5TTS_CLONE" | sed 's/^/      /'
    fi
    
    # Erros
    ERRORS=$(grep -i "error\|failed" "$LOG_FILE" | grep -v "Failed to open connection" | tail -3)
    if [ -n "$ERRORS" ]; then
        echo ""
        echo "   ⚠️  Possíveis erros:"
        echo "$ERRORS" | sed 's/^/      /'
    fi
    
    echo ""
    echo "========================================="
    echo "Tamanho do log: $(wc -l < "$LOG_FILE") linhas"
    echo "Última atualização: $(date '+%H:%M:%S')"
}

# Loop de monitoramento
while true; do
    clear
    show_progress
    
    # Verifica se build finalizou
    if grep -q "Successfully built\|ERROR\|FAILED" "$LOG_FILE"; then
        echo ""
        if grep -q "Successfully built" "$LOG_FILE"; then
            echo "✅ BUILD CONCLUÍDO COM SUCESSO!"
            IMAGE_ID=$(grep "Successfully built" "$LOG_FILE" | tail -1 | awk '{print $NF}')
            echo "   Image ID: $IMAGE_ID"
        else
            echo "❌ BUILD FALHOU"
        fi
        break
    fi
    
    sleep 5
done
