# Script de Teste - Limpeza Total dos Microserviços
# Testa se o endpoint /admin/cleanup está funcionando corretamente

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "🧪 TESTE DE LIMPEZA TOTAL DOS MICROSERVIÇOS" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# URLs dos microserviços
$VIDEO_DOWNLOADER = "http://localhost:8001"
$AUDIO_NORMALIZATION = "http://localhost:8002"
$AUDIO_TRANSCRIBER = "http://localhost:8003"

# Função para verificar se serviço está rodando
function Test-Service {
    param($name, $url)
    
    Write-Host "Verificando $name... " -NoNewline
    try {
        $response = Invoke-RestMethod -Uri "$url/health" -Method Get -ErrorAction Stop
        Write-Host "✓ Online" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "✗ Offline" -ForegroundColor Red
        return $false
    }
}

# Função para obter estatísticas
function Get-ServiceStats {
    param($name, $url)
    
    Write-Host ""
    Write-Host "📊 Estatísticas de $name ANTES da limpeza:" -ForegroundColor Yellow
    try {
        $stats = Invoke-RestMethod -Uri "$url/admin/stats" -Method Get
        $stats | ConvertTo-Json -Depth 10
    } catch {
        Write-Host "Erro ao obter estatísticas: $_" -ForegroundColor Red
    }
}

# Função para executar limpeza
function Invoke-Cleanup {
    param($name, $url)
    
    Write-Host ""
    Write-Host "🔥 Executando limpeza em $name..." -ForegroundColor Yellow
    
    # Medir tempo de resposta
    $start = Get-Date
    try {
        $response = Invoke-RestMethod -Uri "$url/admin/cleanup" -Method Post
        $end = Get-Date
        $duration = ($end - $start).TotalSeconds
        
        Write-Host "Resposta:"
        $response | ConvertTo-Json -Depth 10
        
        Write-Host ""
        Write-Host "⏱️  Tempo de resposta: $([math]::Round($duration, 3))s" -ForegroundColor Green
        
        # Validar tempo de resposta (deve ser < 1s)
        if ($duration -lt 1.0) {
            Write-Host "✓ Resposta resiliente (< 1s)" -ForegroundColor Green
        } else {
            Write-Host "✗ Resposta lenta (> 1s)" -ForegroundColor Red
        }
    } catch {
        Write-Host "Erro na limpeza: $_" -ForegroundColor Red
    }
}

# Função para verificar se limpou
function Test-CleanupResult {
    param($name, $url)
    
    Write-Host ""
    Write-Host "📊 Estatísticas de $name APÓS a limpeza:" -ForegroundColor Yellow
    try {
        $stats = Invoke-RestMethod -Uri "$url/admin/stats" -Method Get
        $stats | ConvertTo-Json -Depth 10
        
        $totalJobs = if ($stats.total_jobs) { $stats.total_jobs } else { 0 }
        
        Write-Host ""
        if ($totalJobs -eq 0) {
            Write-Host "✓ Redis zerado (0 jobs)" -ForegroundColor Green
        } else {
            Write-Host "✗ Redis ainda tem $totalJobs jobs" -ForegroundColor Red
        }
    } catch {
        Write-Host "Erro ao verificar resultado: $_" -ForegroundColor Red
    }
}

Write-Host "======================================================================"
Write-Host "1. Verificando serviços..."
Write-Host "======================================================================"

$servicesOk = $true

$servicesOk = (Test-Service "Video Downloader" $VIDEO_DOWNLOADER) -and $servicesOk
$servicesOk = (Test-Service "Audio Normalization" $AUDIO_NORMALIZATION) -and $servicesOk
$servicesOk = (Test-Service "Audio Transcriber" $AUDIO_TRANSCRIBER) -and $servicesOk

if (-not $servicesOk) {
    Write-Host ""
    Write-Host "❌ Alguns serviços estão offline. Inicie-os com:" -ForegroundColor Red
    Write-Host "   docker compose up -d"
    exit 1
}

Write-Host ""
Write-Host "======================================================================"
Write-Host "2. Estatísticas ANTES da limpeza"
Write-Host "======================================================================"

Get-ServiceStats "Video Downloader" $VIDEO_DOWNLOADER
Get-ServiceStats "Audio Normalization" $AUDIO_NORMALIZATION
Get-ServiceStats "Audio Transcriber" $AUDIO_TRANSCRIBER

Write-Host ""
Write-Host "======================================================================"
Write-Host "3. Executando limpeza TOTAL"
Write-Host "======================================================================"
Write-Host ""
Write-Host "⚠️  ATENÇÃO: Isto irá remover TODOS os jobs, arquivos e modelos!" -ForegroundColor Red
$response = Read-Host "Continuar? (y/N)"

if ($response -notmatch '^[Yy]$') {
    Write-Host "Operação cancelada."
    exit 0
}

Invoke-Cleanup "Video Downloader" $VIDEO_DOWNLOADER
Write-Host ""
Write-Host "⏳ Aguardando limpeza completar..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Invoke-Cleanup "Audio Normalization" $AUDIO_NORMALIZATION
Write-Host ""
Write-Host "⏳ Aguardando limpeza completar..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Invoke-Cleanup "Audio Transcriber" $AUDIO_TRANSCRIBER
Write-Host ""
Write-Host "⏳ Aguardando limpeza completar..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "======================================================================"
Write-Host "4. Verificando resultados"
Write-Host "======================================================================"

Test-CleanupResult "Video Downloader" $VIDEO_DOWNLOADER
Test-CleanupResult "Audio Normalization" $AUDIO_NORMALIZATION
Test-CleanupResult "Audio Transcriber" $AUDIO_TRANSCRIBER

Write-Host ""
Write-Host "======================================================================"
Write-Host "5. Verificando logs"
Write-Host "======================================================================"
Write-Host ""
Write-Host "📝 Logs recentes:" -ForegroundColor Yellow
Write-Host ""

Write-Host "--- Video Downloader ---"
docker compose logs --tail=20 video-downloader 2>$null | Select-String -Pattern "limpeza|cleanup" -CaseSensitive:$false

Write-Host ""
Write-Host "--- Audio Normalization ---"
docker compose logs --tail=20 audio-normalization 2>$null | Select-String -Pattern "limpeza|cleanup" -CaseSensitive:$false

Write-Host ""
Write-Host "--- Audio Transcriber ---"
docker compose logs --tail=20 audio-transcriber 2>$null | Select-String -Pattern "limpeza|cleanup" -CaseSensitive:$false

Write-Host ""
Write-Host "======================================================================"
Write-Host "✅ TESTE CONCLUÍDO" -ForegroundColor Green
Write-Host "======================================================================"
Write-Host ""
Write-Host "Para ver logs completos:"
Write-Host "  docker compose logs -f video-downloader"
Write-Host "  docker compose logs -f audio-normalization"
Write-Host "  docker compose logs -f audio-transcriber"
Write-Host ""
