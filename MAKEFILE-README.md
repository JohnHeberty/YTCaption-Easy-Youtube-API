 Makefile - Guia de Uso

## 📋 Visão Geral

Este Makefile fornece uma interface unificada para gerenciar todos os serviços do projeto YTCaption-Easy-Youtube-API.

## 🚀 Comandos Principais

### Ajuda e Informações

```bash
make help              # Mostra todos os comandos disponíveis
make list-services     # Lista todos os serviços
make docker-info       # Informaçõe => [celery-worker] resolving provenance for metadata file                                                                                                 0.0s
 => [audio-normalization-service] resolving provenance for metadata file                                                                                   0.0s
[+] Running 5/5
 ✔ audio-normalization-celery-worker                Built                                                                                                  0.0s 
 ✔ audio-normalization-audio-normalization-service  Built                                                                                                  0.0s 
 ✔ Network audio-normalization_default              Created                                                                                                0.0s 
 ✔ Container audio-normalization-api                Created                                                                                                0.1s 
 ✔ Container audio-normalization-celery             Created                                                                                                0.0s 
Attaching to audio-normalization-api, audio-normalization-celery
Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint audio-normalization-api (4a812dc42838cd08df483267d046dbc788c6c172ed3e95895a534c7ca6771f61): Bind for 0.0.0.0:8002 failed: port is already allocateds do Docker
make check-ports       # Verifica portas em uso
```

### Validação (SEM iniciar serviços)

```bash
make validate          # Validação completa do projeto
make test-syntax       # Valida sintaxe do Makefile
make validate-docker-compose    # Valida docker-compose.yml
make validate-dockerfiles       # Valida Dockerfiles
make validate-env-files         # Valida arquivos .env
make test-requirements          # Valida requirements.txt
```

### Instalação e Setup

```bash
make install           # Instala todas as dependências
make create-venv       # Cria ambiente virtual Python
make install-requirements  # Instala requirements
make dev-setup         # Setup completo para desenvolvimento
```

### Build e Deploy

```bash
make build             # Build de todos os serviços
make build-youtube-search      # Build de serviço específico
make up                # Inicia todos os serviços
make up-youtube-search         # Inicia serviço específico
make down              # Para todos os serviços
make down-youtube-search       # Para serviço específico
make restart           # Reinicia todos os serviços
make restart-youtube-search    # Reinicia serviço específico
```

### Monitoramento

```bash
make status            # Status de todos os containers
make status-youtube-search     # Status de serviço específico
make logs              # Logs de todos os serviços
make logs-youtube-search       # Logs de serviço específico
make healthcheck       # Verifica health dos serviços
```

### Limpeza

```bash
make clean             # Remove containers e imagens não utilizadas
make clean-venv        # Remove ambiente virtual
make clean-all         # Limpeza completa
```

### Git

```bash
make git-status        # Status do git
make git-push          # Commit e push
```

### Testes

```bash
make test              # Executa testes de todos os serviços
```

## 📦 Serviços Disponíveis

- **audio-normalization** - Normalização de áudio
- **audio-transcriber** - Transcrição de áudio
- **make-video** - Criação de vídeos
- **video-downloader** - Download de vídeos
- **youtube-search** - Busca no YouTube

## 🔧 Exemplos de Uso

### Workflow de Desenvolvimento

```bash
# 1. Validar projeto (sem iniciar)
make validate

# 2. Setup de desenvolvimento
make dev-setup

# 3. Build dos serviços
make build

# 4. Iniciar serviços
make up

# 5. Verificar status
make status

# 6. Ver logs
make logs-youtube-search
```

### Workflow de Deploy

```bash
# Build e deploy de serviço específico
make build-youtube-search
make up-youtube-search
make status-youtube-search
make healthcheck
```

### Workflow de Debug

```bash
# Verificar problema em serviço
make status-youtube-search
make logs-youtube-search

# Reiniciar serviço
make restart-youtube-search

# Ver logs em tempo real
make logs-youtube-search
```

### Limpeza e Manutenção

```bash
# Limpeza básica
make clean

# Limpeza completa (incluindo venv)
make clean-all

# Rebuild completo
make clean
make build
make up
```

## 🎯 Validação Antes de Deploy

**SEMPRE** valide o projeto antes de fazer deploy:

```bash
make validate
```

Este comando verifica:
- ✅ Sintaxe do Makefile
- ✅ Arquivos docker-compose.yml
- ✅ Dockerfiles
- ✅ Arquivos .env
- ✅ Requirements.txt

## 📝 Notas Importantes

1. **Validação**: O comando `make validate` NÃO inicia nenhum serviço, apenas valida os arquivos
2. **Ambiente Virtual**: O Makefile cria e usa um venv automaticamente se necessário
3. **Serviços Individuais**: Use o padrão `make comando-nome-servico` para operações em serviços específicos
4. **Cores**: O output usa cores para facilitar a leitura (verde=sucesso, amarelo=aviso, vermelho=erro)

## 🐛 Troubleshooting

### Erro: "Serviço não encontrado"
```bash
# Verifique os serviços disponíveis
make list-services
```

### Erro: "Docker não disponível"
```bash
# Verifique instalação do Docker
make docker-info
```

### Erro: "Porta em uso"
```bash
# Verifique portas em uso
make check-ports
```

## 📚 Estrutura do Projeto

```
YTCaption-Easy-Youtube-API/
├── Makefile                    # Este arquivo
├── docker-compose.yml          # Compose principal
├── services/
│   ├── audio-normalization/
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── .env
│   ├── audio-transcriber/
│   ├── make-video/
│   ├── video-downloader/
│   └── youtube-search/
└── .venv/                      # Ambiente virtual (criado automaticamente)
```

## 🔐 Segurança

- Arquivos `.env` são validados mas nunca exibidos
- Credenciais devem estar nos arquivos `.env` de cada serviço
- Use `.env.example` como template

## 📄 Licença

Este Makefile faz parte do projeto YTCaption-Easy-Youtube-API
