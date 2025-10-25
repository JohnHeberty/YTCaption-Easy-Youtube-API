#!/usr/bin/env pwsh
# YTCaption Management Script for Windows
# Equivalente ao Makefile para ambiente Windows

param(
    [Parameter(Position=0)]
    [ValidateSet('help', 'build', 'up', 'down', 'restart', 'logs', 'status', 'clean', 'test', 'setup', 'stats', 'cleanup-cache', 'dev', 'backup')]
    [string]$Command = 'help'
)

$COMPOSE_FILE = "docker-compose.yml"
$SERVICES = @("video-downloader", "audio-normalization", "audio-transcriber")

function Show-Help {
    Write-Host "YTCaption - Easy YouTube API Management Script" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Comandos disponíveis:" -ForegroundColor Green
    Write-Host "  help           - Mostra esta ajuda"
    Write-Host "  build          - Constrói todas as imagens Docker"
    Write-Host "  up             - Inicia todos os serviços"
    Write-Host "  down           - Para todos os serviços"  
    Write-Host "  restart        - Reinicia todos os serviços"
    Write-Host "  logs           - Mostra logs de todos os serviços"
    Write-Host "  status         - Mostra status dos serviços"
    Write-Host "  clean          - Remove containers e volumes não utilizados"
    Write-Host "  test           - Executa testes básicos nos endpoints"
    Write-Host "  setup          - Configuração inicial completa"
    Write-Host "  stats          - Mostra estatísticas dos serviços"
    Write-Host "  cleanup-cache  - Limpa cache de todos os serviços"
    Write-Host "  dev            - Inicia em modo desenvolvimento"
    Write-Host "  backup         - Faz backup dos dados"
    Write-Host ""
    Write-Host "Exemplo: .\manage.ps1 up" -ForegroundColor Yellow
}

function Build-Images {
    Write-Host "🔨 Construindo imagens Docker..." -ForegroundColor Blue
    docker-compose -f $COMPOSE_FILE build --no-cache
    Write-Host "✅ Imagens construídas com sucesso!" -ForegroundColor Green
}

function Start-Services {
    Write-Host "🚀 Iniciando serviços..." -ForegroundColor Blue
    
    # Cria rede se não existir
    docker network create ytcaption-network 2>$null
    
    docker-compose -f $COMPOSE_FILE up -d
    
    Write-Host "✅ Serviços iniciados!" -ForegroundColor Green
    Write-Host "🔗 Video Downloader: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "🔗 Audio Normalization: http://localhost:8001" -ForegroundColor Cyan
    Write-Host "🔗 Audio Transcriber: http://localhost:8002" -ForegroundColor Cyan
}

function Stop-Services {
    Write-Host "🛑 Parando serviços..." -ForegroundColor Blue
    docker-compose -f $COMPOSE_FILE down
    Write-Host "🛑 Serviços parados!" -ForegroundColor Green
}

function Restart-Services {
    Stop-Services
    Start-Services
}

function Show-Logs {
    Write-Host "📋 Mostrando logs (Ctrl+C para sair)..." -ForegroundColor Blue
    docker-compose -f $COMPOSE_FILE logs -f
}

function Show-Status {
    Write-Host "📊 Status dos Serviços:" -ForegroundColor Blue
    docker-compose -f $COMPOSE_FILE ps
    
    Write-Host ""
    Write-Host "Health Checks:" -ForegroundColor Green
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        Write-Host "✅ Video Downloader (8000): OK" -ForegroundColor Green
    } catch {
        Write-Host "❌ Video Downloader (8000): Não acessível" -ForegroundColor Red
    }
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8001/health" -TimeoutSec 5
        Write-Host "✅ Audio Normalization (8001): OK" -ForegroundColor Green
    } catch {
        Write-Host "❌ Audio Normalization (8001): Não acessível" -ForegroundColor Red
    }
    
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8002/health" -TimeoutSec 5
        Write-Host "✅ Audio Transcriber (8002): OK" -ForegroundColor Green
    } catch {
        Write-Host "❌ Audio Transcriber (8002): Não acessível" -ForegroundColor Red
    }
}

function Clean-System {
    Write-Host "🧹 Limpando sistema..." -ForegroundColor Blue
    docker-compose -f $COMPOSE_FILE down -v
    docker system prune -f
    docker volume prune -f
    Write-Host "🧹 Limpeza concluída!" -ForegroundColor Green
}

function Test-Endpoints {
    Write-Host "🧪 Testando endpoints..." -ForegroundColor Blue
    
    $endpoints = @(
        @{ Name = "Video Downloader"; Url = "http://localhost:8000/health" },
        @{ Name = "Audio Normalization"; Url = "http://localhost:8001/health" },
        @{ Name = "Audio Transcriber"; Url = "http://localhost:8002/health" }
    )
    
    foreach ($endpoint in $endpoints) {
        try {
            $response = Invoke-RestMethod -Uri $endpoint.Url -TimeoutSec 5
            Write-Host "✅ $($endpoint.Name): OK (200)" -ForegroundColor Green
        } catch {
            Write-Host "❌ $($endpoint.Name): Falhou" -ForegroundColor Red
        }
    }
}

function Setup-Environment {
    Write-Host "🚀 Configuração inicial..." -ForegroundColor Blue
    
    # Verifica dependências
    $dependencies = @("docker", "docker-compose")
    foreach ($dep in $dependencies) {
        if (!(Get-Command $dep -ErrorAction SilentlyContinue)) {
            Write-Host "❌ $dep não encontrado. Instale primeiro." -ForegroundColor Red
            return
        }
    }
    
    # Verifica Redis
    Write-Host "🔍 Verificando Redis em 192.168.18.110:6379..." -ForegroundColor Blue
    try {
        $redis = New-Object System.Net.Sockets.TcpClient
        $redis.Connect("192.168.18.110", 6379)
        $redis.Close()
        Write-Host "✅ Redis conectado!" -ForegroundColor Green
    } catch {
        Write-Host "❌ Redis não acessível em 192.168.18.110:6379" -ForegroundColor Red
    }
    
    # Cria diretórios
    Write-Host "📁 Criando diretórios..." -ForegroundColor Blue
    $directories = @(
        "services\video-downloader\cache",
        "services\video-downloader\logs",
        "services\audio-normalization\uploads",
        "services\audio-normalization\processed", 
        "services\audio-normalization\temp",
        "services\audio-normalization\logs",
        "services\audio-transcriber\uploads",
        "services\audio-transcriber\transcriptions",
        "services\audio-transcriber\models",
        "services\audio-transcriber\temp",
        "services\audio-transcriber\logs",
        "backups"
    )
    
    foreach ($dir in $directories) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    # Cria rede Docker
    docker network create ytcaption-network 2>$null
    
    Write-Host "✅ Setup concluído! Execute '.\manage.ps1 up' para iniciar os serviços." -ForegroundColor Green
}

function Show-Stats {
    Write-Host "📊 Estatísticas dos Serviços:" -ForegroundColor Blue
    
    $services = @(
        @{ Name = "Video Downloader"; Url = "http://localhost:8000/admin/stats" },
        @{ Name = "Audio Normalization"; Url = "http://localhost:8001/admin/stats" },
        @{ Name = "Audio Transcriber"; Url = "http://localhost:8002/admin/stats" }
    )
    
    foreach ($service in $services) {
        Write-Host ""
        Write-Host "$($service.Name):" -ForegroundColor Cyan
        try {
            $response = Invoke-RestMethod -Uri $service.Url -TimeoutSec 5
            $response | ConvertTo-Json -Depth 3
        } catch {
            Write-Host "  Não disponível" -ForegroundColor Red
        }
    }
}

function Clear-Cache {
    Write-Host "🧹 Limpando cache dos serviços..." -ForegroundColor Blue
    
    $cacheEndpoints = @(
        "http://localhost:8000/admin/cache",
        "http://localhost:8001/admin/cache", 
        "http://localhost:8002/admin/cache"
    )
    
    foreach ($endpoint in $cacheEndpoints) {
        try {
            Invoke-RestMethod -Uri $endpoint -Method DELETE -TimeoutSec 5
            Write-Host "✅ Cache limpo: $endpoint" -ForegroundColor Green
        } catch {
            Write-Host "❌ Falha ao limpar: $endpoint" -ForegroundColor Red
        }
    }
    
    Write-Host "✅ Cache limpo!" -ForegroundColor Green
}

function Start-Dev {
    Write-Host "🔧 Iniciando modo desenvolvimento..." -ForegroundColor Blue
    
    # Cria rede se não existir  
    docker network create ytcaption-network 2>$null
    
    docker-compose -f $COMPOSE_FILE up --build
}

function Create-Backup {
    Write-Host "💾 Criando backup..." -ForegroundColor Blue
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = "backups\$timestamp"
    
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    
    foreach ($service in $SERVICES) {
        $uploadDir = "services\$service\uploads"
        $processedDir = "services\$service\processed"
        
        if (Test-Path $uploadDir) {
            Copy-Item -Path $uploadDir -Destination "$backupDir\$service-uploads" -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        if (Test-Path $processedDir) {
            Copy-Item -Path $processedDir -Destination "$backupDir\$service-processed" -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host "✅ Backup criado em $backupDir" -ForegroundColor Green
}

# Executa o comando
switch ($Command) {
    'help' { Show-Help }
    'build' { Build-Images }
    'up' { Start-Services }
    'down' { Stop-Services }
    'restart' { Restart-Services }
    'logs' { Show-Logs }
    'status' { Show-Status }
    'clean' { Clean-System }
    'test' { Test-Endpoints }
    'setup' { Setup-Environment }
    'stats' { Show-Stats }
    'cleanup-cache' { Clear-Cache }
    'dev' { Start-Dev }
    'backup' { Create-Backup }
    default { 
        Write-Host "Comando desconhecido: $Command" -ForegroundColor Red
        Show-Help 
    }
}