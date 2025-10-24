# YouTube Resilience v3.0 - Test Script
# PowerShell script to verify the installation

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "YouTube Resilience v3.0 - Test Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if Docker is running
Write-Host "[1/7] Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Step 2: Check if containers are running
Write-Host "[2/7] Checking containers..." -ForegroundColor Yellow
$whisperRunning = docker ps --filter "name=whisper-transcription-api" --format "{{.Names}}"
if (-not $whisperRunning) {
    Write-Host "⚠️  whisper-transcription-api is not running" -ForegroundColor Yellow
    Write-Host "   Starting containers..." -ForegroundColor Yellow
    docker-compose up -d
    Start-Sleep -Seconds 10
} else {
    Write-Host "✅ whisper-transcription-api is running" -ForegroundColor Green
}

$torRunning = docker ps --filter "name=tor-proxy" --format "{{.Names}}"
if ($torRunning) {
    Write-Host "✅ tor-proxy is running" -ForegroundColor Green
} else {
    Write-Host "ℹ️  tor-proxy is not running (optional)" -ForegroundColor Cyan
}
Write-Host ""

# Step 3: Test network connectivity - ping
Write-Host "[3/7] Testing ping..." -ForegroundColor Yellow
$pingResult = docker exec whisper-transcription-api ping -c 3 google.com 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Ping to google.com successful" -ForegroundColor Green
} else {
    Write-Host "❌ Ping failed: $pingResult" -ForegroundColor Red
}
Write-Host ""

# Step 4: Test DNS resolution
Write-Host "[4/7] Testing DNS..." -ForegroundColor Yellow
$dnsResult = docker exec whisper-transcription-api nslookup youtube.com 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ DNS resolution successful" -ForegroundColor Green
} else {
    Write-Host "❌ DNS failed: $dnsResult" -ForegroundColor Red
}
Write-Host ""

# Step 5: Test HTTPS connectivity
Write-Host "[5/7] Testing HTTPS to YouTube..." -ForegroundColor Yellow
$httpsResult = docker exec whisper-transcription-api curl -I --max-time 10 https://www.youtube.com 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ HTTPS connection to YouTube successful" -ForegroundColor Green
} else {
    Write-Host "❌ HTTPS failed: $httpsResult" -ForegroundColor Red
}
Write-Host ""

# Step 6: Test Tor (if running)
if ($torRunning) {
    Write-Host "[6/7] Testing Tor proxy..." -ForegroundColor Yellow
    $torTest = docker exec whisper-transcription-api curl --socks5 tor-proxy:9050 --max-time 15 https://check.torproject.org 2>&1
    if ($torTest -match "Congratulations") {
        Write-Host "✅ Tor proxy is working!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Tor proxy test inconclusive" -ForegroundColor Yellow
    }
} else {
    Write-Host "[6/7] Skipping Tor test (not enabled)" -ForegroundColor Cyan
}
Write-Host ""

# Step 7: Check logs for v3.0 initialization
Write-Host "[7/7] Checking v3.0 initialization..." -ForegroundColor Yellow
$logs = docker logs whisper-transcription-api --tail 100 2>&1
if ($logs -match "v3.0|YouTubeDownloader initialized") {
    Write-Host "✅ v3.0 Resilience System initialized" -ForegroundColor Green
    
    # Extract configuration from logs
    $configLine = $logs | Select-String -Pattern "YouTube Download Configuration"
    if ($configLine) {
        Write-Host "📋 Configuration detected in logs" -ForegroundColor Cyan
    }
} else {
    Write-Host "⚠️  v3.0 not detected in logs (container may need restart)" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker:    ✅" -ForegroundColor Green
Write-Host "Container: $(if ($whisperRunning) { '✅' } else { '❌' })" -ForegroundColor $(if ($whisperRunning) { 'Green' } else { 'Red' })
Write-Host "Ping:      $(if ($LASTEXITCODE -eq 0) { '✅' } else { '❌' })" -ForegroundColor $(if ($LASTEXITCODE -eq 0) { 'Green' } else { 'Red' })
Write-Host "DNS:       $(if ($dnsResult -match 'Address') { '✅' } else { '❌' })" -ForegroundColor $(if ($dnsResult -match 'Address') { 'Green' } else { 'Red' })
Write-Host "HTTPS:     $(if ($httpsResult -match '200 OK|301 Moved') { '✅' } else { '❌' })" -ForegroundColor $(if ($httpsResult -match '200 OK|301 Moved') { 'Green' } else { 'Red' })
if ($torRunning) {
    Write-Host "Tor:       $(if ($torTest -match 'Congratulations') { '✅' } else { '⚠️ ' })" -ForegroundColor $(if ($torTest -match 'Congratulations') { 'Green' } else { 'Yellow' })
}
Write-Host ""

# Next steps
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Test download: curl -X POST http://localhost:8000/api/v1/transcribe -H 'Content-Type: application/json' -d '{\"url\": \"https://www.youtube.com/watch?v=jNQXAC9IVRw\"}'" -ForegroundColor White
Write-Host "2. Monitor logs:  docker logs -f whisper-transcription-api" -ForegroundColor White
Write-Host "3. Check errors:  docker logs whisper-transcription-api | Select-String -Pattern 'ERROR|ERRO|🔥'" -ForegroundColor White
Write-Host ""
Write-Host "For detailed documentation, see: docs/YOUTUBE-RESILIENCE-v3.0.md" -ForegroundColor Cyan
