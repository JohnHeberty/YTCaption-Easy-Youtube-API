# 🚀 Script de Deploy - Atualizar Servidor com Código Corrigido
# Data: 2025-10-19

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "🚀 DEPLOY - Whisper Transcription API" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Configurações
$SERVER_IP = "192.168.18.104"
$PROJECT_PATH = "/root/YTCaption-Easy-Youtube-API"  # Ajuste conforme necessário

Write-Host "📋 Informações do Deploy:" -ForegroundColor Yellow
Write-Host "  Servidor: $SERVER_IP" -ForegroundColor White
Write-Host "  Projeto: $PROJECT_PATH" -ForegroundColor White
Write-Host ""

Write-Host "⚠️  IMPORTANTE:" -ForegroundColor Red
Write-Host "  Este script assume que você tem acesso SSH ao servidor." -ForegroundColor White
Write-Host "  Certifique-se de ter feito 'git push' antes de executar!" -ForegroundColor White
Write-Host ""

# Verificar se há mudanças não commitadas localmente
Write-Host "🔍 Verificando estado local do Git..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "❌ ERRO: Há mudanças não commitadas!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Arquivos modificados:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    Write-Host "Execute antes de continuar:" -ForegroundColor Yellow
    Write-Host "  git add ." -ForegroundColor White
    Write-Host "  git commit -m 'fix: correções singleton e parallel mode'" -ForegroundColor White
    Write-Host "  git push origin main" -ForegroundColor White
    exit 1
}

Write-Host "✅ Git limpo - tudo commitado" -ForegroundColor Green
Write-Host ""

# Perguntar se já fez push
Write-Host "❓ Você já fez 'git push origin main'? (S/N): " -ForegroundColor Yellow -NoNewline
$pushed = Read-Host

if ($pushed -ne "S" -and $pushed -ne "s") {
    Write-Host "❌ Faça push antes de continuar!" -ForegroundColor Red
    Write-Host "  git push origin main" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "🔄 Comandos que serão executados no servidor:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. cd $PROJECT_PATH" -ForegroundColor Gray
Write-Host "2. docker-compose down" -ForegroundColor Gray
Write-Host "3. git pull origin main" -ForegroundColor Gray
Write-Host "4. docker-compose build --no-cache" -ForegroundColor Gray
Write-Host "5. docker-compose up -d" -ForegroundColor Gray
Write-Host "6. docker-compose logs -f" -ForegroundColor Gray
Write-Host ""

Write-Host "❓ Continuar com o deploy? (S/N): " -ForegroundColor Yellow -NoNewline
$confirm = Read-Host

if ($confirm -ne "S" -and $confirm -ne "s") {
    Write-Host "❌ Deploy cancelado." -ForegroundColor Red
    exit 0
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "🚀 INICIANDO DEPLOY..." -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Comandos para executar no servidor
$deployCommands = @"
cd $PROJECT_PATH && \
echo '🛑 Parando containers...' && \
docker-compose down && \
echo '📥 Atualizando código...' && \
git pull origin main && \
echo '🏗️  Rebuilding containers (pode demorar 2-3min)...' && \
docker-compose build --no-cache && \
echo '▶️  Iniciando containers...' && \
docker-compose up -d && \
sleep 5 && \
echo '' && \
echo '=====================================' && \
echo '📊 LOGS DE STARTUP (Ctrl+C para sair):' && \
echo '=====================================' && \
docker-compose logs -f
"@

Write-Host "📡 Conectando ao servidor via SSH..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Executando comandos remotos..." -ForegroundColor Gray
Write-Host ""

# Executar via SSH
ssh root@$SERVER_IP $deployCommands

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "✅ DEPLOY FINALIZADO!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Próximos passos:" -ForegroundColor Yellow
Write-Host "  1. Verificar se os logs mostram 'PARALLEL MODE ENABLED'" -ForegroundColor White
Write-Host "  2. Verificar se 2 workers foram iniciados" -ForegroundColor White
Write-Host "  3. Verificar se o modelo foi carregado 2x" -ForegroundColor White
Write-Host "  4. Fazer requisição de teste" -ForegroundColor White
Write-Host ""
Write-Host "🔍 Para verificar logs novamente:" -ForegroundColor Yellow
Write-Host "  ssh root@$SERVER_IP 'cd $PROJECT_PATH && docker-compose logs -f'" -ForegroundColor White
Write-Host ""
