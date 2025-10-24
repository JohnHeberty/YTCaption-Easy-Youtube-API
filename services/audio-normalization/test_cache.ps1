#!/usr/bin/env pwsh
# Script de teste do sistema de cache

Write-Host "🧪 Testando Sistema de Cache de Audio Normalization" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8001"

# Verifica se serviço está rodando
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health"
    Write-Host "✅ Serviço está rodando" -ForegroundColor Green
} catch {
    Write-Host "❌ Serviço não está rodando. Execute: docker-compose up -d" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📝 Teste 1: Upload do mesmo arquivo 2x (deve usar cache)" -ForegroundColor Yellow
Write-Host ""

# Cria arquivo de teste
$testFile = "test_audio.txt"
"Este é um arquivo de teste de áudio" | Out-File -FilePath $testFile -Encoding UTF8

Write-Host "📤 Request 1: Primeiro upload" -ForegroundColor Cyan
$file1 = Get-Item $testFile
$form1 = @{
    file = $file1
    remove_noise = "true"
    normalize_volume = "true"
    convert_to_mono = "true"
}

$response1 = Invoke-RestMethod -Method Post -Uri "$baseUrl/normalize" -Form $form1
$jobId1 = $response1.id
Write-Host "   Job ID: $jobId1" -ForegroundColor White
Write-Host "   Status: $($response1.status)" -ForegroundColor White

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "📤 Request 2: Mesmo arquivo, mesmas operações" -ForegroundColor Cyan
$file2 = Get-Item $testFile
$form2 = @{
    file = $file2
    remove_noise = "true"
    normalize_volume = "true"
    convert_to_mono = "true"
}

$response2 = Invoke-RestMethod -Method Post -Uri "$baseUrl/normalize" -Form $form2
$jobId2 = $response2.id
Write-Host "   Job ID: $jobId2" -ForegroundColor White
Write-Host "   Status: $($response2.status)" -ForegroundColor White

if ($jobId1 -eq $jobId2) {
    Write-Host ""
    Write-Host "✅ CACHE HIT! Mesmo Job ID retornado" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ CACHE MISS! Job IDs diferentes" -ForegroundColor Red
}

Write-Host ""
Write-Host "📝 Teste 2: Mesmo arquivo, operações diferentes (não deve usar cache)" -ForegroundColor Yellow
Write-Host ""

Write-Host "📤 Request 3: Apenas remove noise" -ForegroundColor Cyan
$file3 = Get-Item $testFile
$form3 = @{
    file = $file3
    remove_noise = "true"
    normalize_volume = "false"
    convert_to_mono = "false"
}

$response3 = Invoke-RestMethod -Method Post -Uri "$baseUrl/normalize" -Form $form3
$jobId3 = $response3.id
Write-Host "   Job ID: $jobId3" -ForegroundColor White
Write-Host "   Status: $($response3.status)" -ForegroundColor White

if ($jobId1 -ne $jobId3) {
    Write-Host ""
    Write-Host "✅ CORRETO! Job IDs diferentes (operações diferentes)" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ ERRO! Mesmo Job ID (deveria ser diferente)" -ForegroundColor Red
}

Write-Host ""
Write-Host "📊 Estatísticas do Sistema:" -ForegroundColor Yellow
$stats = Invoke-RestMethod -Uri "$baseUrl/admin/stats"
Write-Host "   Total de Jobs: $($stats.total_jobs)" -ForegroundColor White
Write-Host "   Por Status:" -ForegroundColor White
foreach ($status in $stats.by_status.PSObject.Properties) {
    Write-Host "     - $($status.Name): $($status.Value)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📋 Jobs Criados:" -ForegroundColor Yellow
Write-Host "   1. $jobId1 (todas operações)" -ForegroundColor White
Write-Host "   2. $jobId2 (cache hit)" -ForegroundColor White
Write-Host "   3. $jobId3 (apenas noise)" -ForegroundColor White

# Remove arquivo de teste
Remove-Item $testFile -Force

Write-Host ""
Write-Host "✅ Testes concluídos!" -ForegroundColor Green
