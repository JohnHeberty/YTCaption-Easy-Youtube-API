# Script para instalar FFmpeg no Windows
Write-Host "Baixando FFmpeg..." -ForegroundColor Green

$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$downloadPath = "$env:TEMP\ffmpeg.zip"
$extractPath = "C:\ffmpeg"

# Baixar
Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath -UseBasicParsing

Write-Host "Extraindo FFmpeg..." -ForegroundColor Green
Expand-Archive -Path $downloadPath -DestinationPath $env:TEMP\ffmpeg -Force

# Mover para C:\ffmpeg
$ffmpegFolder = Get-ChildItem -Path "$env:TEMP\ffmpeg" -Directory | Select-Object -First 1
if (-not (Test-Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath -Force
}
Copy-Item -Path "$($ffmpegFolder.FullName)\bin\*" -Destination $extractPath -Force

Write-Host "Adicionando ao PATH..." -ForegroundColor Green
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$extractPath*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$extractPath", "User")
}

# Atualizar PATH da sessão atual
$env:Path = "$env:Path;$extractPath"

Write-Host "FFmpeg instalado com sucesso em: $extractPath" -ForegroundColor Green
Write-Host "Testando instalação..." -ForegroundColor Yellow
& ffmpeg -version

Write-Host "`nReinicie o PowerShell ou execute: `$env:Path = `"$env:Path;$extractPath`"" -ForegroundColor Cyan
