# Script de Execução Rápida - Benchmark de Transcrição Paralela
# PowerShell Script para Windows

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🧪 BENCHMARK: Transcrição Paralela" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Detectar CPU cores
$cpuCores = (Get-WmiObject -Class Win32_Processor).NumberOfLogicalProcessors
Write-Host "💻 CPU Cores detectados: $cpuCores" -ForegroundColor Green
Write-Host ""

# Verificar se vídeo de teste existe
$videoPath = ".\temp\test_video.mp3"
if (-not (Test-Path $videoPath)) {
    Write-Host "⚠️  Vídeo de teste não encontrado!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "📥 Deseja baixar um vídeo de teste? (S/N)" -ForegroundColor Yellow
    $download = Read-Host
    
    if ($download -eq "S" -or $download -eq "s") {
        Write-Host ""
        Write-Host "🔗 Cole a URL do YouTube (ou pressione Enter para usar padrão):" -ForegroundColor Cyan
        $url = Read-Host
        
        Write-Host ""
        Write-Host "📥 Baixando vídeo de teste..." -ForegroundColor Green
        
        if ($url) {
            python teste_melhoria\download_test_video.py $url
        } else {
            python teste_melhoria\download_test_video.py
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "❌ Falha ao baixar vídeo!" -ForegroundColor Red
            Write-Host "Certifique-se de ter yt-dlp instalado: pip install yt-dlp" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "❌ Cancelado pelo usuário" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🎯 Escolha o tipo de benchmark:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. Comparação Completa (Single-core vs Multi-core)" -ForegroundColor White
Write-Host "   - Testa método atual + método paralelo" -ForegroundColor Gray
Write-Host "   - Compara qualidade e performance" -ForegroundColor Gray
Write-Host "   - Mais demorado (~3-5 minutos)" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Teste Rápido Multi-Workers (RECOMENDADO)" -ForegroundColor Green
Write-Host "   - Testa apenas método paralelo" -ForegroundColor Gray
Write-Host "   - Múltiplas configurações (1, 2, 4, 8 workers)" -ForegroundColor Gray
Write-Host "   - Mais rápido (~2-4 minutos)" -ForegroundColor Gray
Write-Host ""
Write-Host "Escolha (1 ou 2):" -ForegroundColor Yellow
$choice = Read-Host

Write-Host ""

switch ($choice) {
    "1" {
        Write-Host "🚀 Executando Comparação Completa..." -ForegroundColor Green
        Write-Host ""
        python teste_melhoria\benchmark_parallel_transcription.py
    }
    "2" {
        Write-Host "🚀 Executando Teste Rápido Multi-Workers..." -ForegroundColor Green
        Write-Host ""
        python teste_melhoria\test_multi_workers.py
    }
    default {
        Write-Host "❌ Opção inválida!" -ForegroundColor Red
        exit 1
    }
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Benchmark falhou!" -ForegroundColor Red
    Write-Host "Verifique os logs acima para detalhes" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Benchmark concluído com sucesso!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📚 Para mais informações, consulte:" -ForegroundColor Cyan
Write-Host "   teste_melhoria\README_BENCHMARK.md" -ForegroundColor White
Write-Host ""
