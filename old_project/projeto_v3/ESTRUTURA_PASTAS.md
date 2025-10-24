# 📂 ESTRUTURA DE PASTAS PROJETO_V2

Para começar a implementação, crie a seguinte estrutura de pastas (diretórios vazios por enquanto, será preenchido com código).

---

## Estrutura Recomendada

```
projeto_v2/
│
├── 📄 README.md                    ✅ Criado
├── 📄 ARQUITETURA.md               ✅ Criado
├── 📄 ESPECIFICACAO_SERVICOS.md    ✅ Criado
├── 📄 CONFIGURACAO_RESILIENCIA.md  ✅ Criado
├── 📄 DEPLOYMENT.md                ✅ Criado
├── 📄 MONITORAMENTO.md             ✅ Criado
├── 📄 TESTES.md                    ✅ Criado
├── 📄 GUIA_RAPIDO.md               ✅ Criado
├── 📄 RESUMO_PROJETO_V2.md         ✅ Criado
├── 📄 INDICE.md                    ✅ Criado
├── 📄 ENTREGA_FINAL.md             ✅ Criado
│
├── 📁 services/                    (criar)
│   ├── 📁 api-gateway/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py             (FastAPI app)
│   │   │   ├── 📁 controllers/
│   │   │   │   └── job_controller.py
│   │   │   ├── 📁 services/
│   │   │   ├── 📁 models/
│   │   │   └── 📁 middleware/
│   │   ├── 📁 tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_controllers.py
│   │   │   └── test_services.py
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   ├── 📁 job-manager/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   │   ├── main.py
│   │   │   ├── 📁 services/
│   │   │   ├── 📁 repositories/
│   │   │   └── 📁 models/
│   │   ├── 📁 tests/
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   ├── 📁 downloader/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   ├── 📁 tests/
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   ├── 📁 transcriber/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   ├── 📁 tests/
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   ├── 📁 storage/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   ├── 📁 tests/
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   ├── 📁 notifier/
│   │   ├── 📄 README.md
│   │   ├── 📁 app/
│   │   ├── 📁 tests/
│   │   ├── 📄 requirements.txt
│   │   ├── 📄 Dockerfile
│   │   └── 📄 .dockerignore
│   │
│   └── 📁 admin/
│       ├── 📄 README.md
│       ├── 📁 app/
│       ├── 📁 tests/
│       ├── 📄 requirements.txt
│       ├── 📄 Dockerfile
│       └── 📄 .dockerignore
│
├── 📁 shared/                      (criar)
│   ├── 📄 __init__.py
│   ├── 📁 models/
│   │   ├── __init__.py
│   │   ├── job.py                  (Job model)
│   │   ├── event.py                (Event base)
│   │   └── user.py                 (User model)
│   ├── 📁 events/
│   │   ├── __init__.py
│   │   ├── job_created.py
│   │   ├── job_completed.py
│   │   └── job_failed.py
│   ├── 📁 utils/
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py      (CircuitBreaker class)
│   │   ├── retry.py                (Retry decorator)
│   │   ├── logger.py               (Structured logging)
│   │   ├── tracing.py              (Jaeger tracer)
│   │   └── metrics.py              (Prometheus metrics)
│   └── 📁 exceptions/
│       ├── __init__.py
│       ├── base.py
│       └── circuit_breaker.py
│
├── 📁 infra/                       (criar)
│   ├── 📁 docker/
│   │   ├── 📄 docker-compose.yml   (já tem template em DEPLOYMENT.md)
│   │   ├── 📄 docker-compose.prod.yml
│   │   └── 📄 Makefile
│   │
│   ├── 📁 kubernetes/
│   │   ├── 📄 namespace.yaml
│   │   ├── 📄 postgres-statefulset.yaml
│   │   ├── 📄 api-gateway-deployment.yaml
│   │   ├── 📄 job-manager-deployment.yaml
│   │   ├── 📄 downloader-deployment.yaml
│   │   ├── 📄 transcriber-deployment.yaml
│   │   ├── 📄 storage-deployment.yaml
│   │   ├── 📄 notifier-deployment.yaml
│   │   ├── 📄 admin-deployment.yaml
│   │   ├── 📄 services.yaml
│   │   ├── 📄 hpa.yaml
│   │   ├── 📄 pdb.yaml
│   │   ├── 📄 resource-quotas.yaml
│   │   ├── 📄 secrets.yaml
│   │   └── 📄 kustomization.yaml
│   │
│   ├── 📁 monitoring/
│   │   ├── 📄 prometheus.yml       (config scrape)
│   │   ├── 📄 alert-rules.yml      (alertas)
│   │   ├── 📄 grafana-dashboards.json
│   │   └── 📄 jaeger-config.yml
│   │
│   ├── 📁 backup/
│   │   ├── 📄 backup-postgres.sh
│   │   ├── 📄 restore-postgres.sh
│   │   └── 📄 test-restore.sh
│   │
│   └── 📁 terraform/               (optional)
│       ├── 📄 main.tf
│       ├── 📄 variables.tf
│       └── 📄 outputs.tf
│
├── 📁 tests/                       (criar)
│   ├── 📁 e2e/
│   │   ├── 📄 test_create_job_flow.py
│   │   ├── 📄 test_error_handling.py
│   │   ├── 📄 test_resilience.py
│   │   └── 📄 conftest.py
│   │
│   ├── 📁 load/
│   │   ├── 📄 locustfile.py        (load test com Locust)
│   │   └── 📄 scenarios.py
│   │
│   ├── 📁 fixtures/
│   │   ├── 📄 jobs.json
│   │   ├── 📄 users.json
│   │   └── 📄 events.json
│   │
│   └── 📁 contracts/
│       ├── 📄 test_job_created_event.py
│       └── 📄 test_api_contract.py
│
├── 📁 docs/                        (criar)
│   ├── 📄 RUNBOOK_INCIDENT_RESPONSE.md
│   ├── 📄 RUNBOOK_SCALING.md
│   ├── 📄 RUNBOOK_DATABASE_FAILOVER.md
│   ├── 📄 FAQ.md
│   └── 📁 diagrams/
│       ├── 📄 architecture.drawio
│       ├── 📄 flow_job_creation.drawio
│       └── 📄 saga_flow.drawio
│
├── 📁 .github/                     (criar)
│   └── 📁 workflows/
│       ├── 📄 test.yml             (CI/CD pipeline)
│       ├── 📄 deploy-staging.yml
│       └── 📄 deploy-prod.yml
│
├── 📄 .gitignore                   (criar)
├── 📄 .env.example                 (criar)
├── 📄 docker-compose.yml           (criar)
├── 📄 Makefile                     (criar - atalhos)
├── 📄 pyproject.toml               (opcional, for poetry)
├── 📄 requirements-base.txt        (criar)
├── 📄 requirements-dev.txt         (criar)
└── 📄 VERSION                      (criar - v2.0.0)
```

---

## Arquivos a Criar (Passo a Passo)

### Passo 1: Criar diretórios

```bash
# Linux/Mac
mkdir -p projeto_v2/services/{api-gateway,job-manager,downloader,transcriber,storage,notifier,admin}/{app,tests}
mkdir -p projeto_v2/shared/{models,events,utils,exceptions}
mkdir -p projeto_v2/infra/{docker,kubernetes,monitoring,backup,terraform}
mkdir -p projeto_v2/tests/{e2e,load,fixtures,contracts}
mkdir -p projeto_v2/docs/diagrams
mkdir -p projeto_v2/.github/workflows

# Windows PowerShell
$dirs = @(
    'services/api-gateway/app',
    'services/api-gateway/tests',
    'services/job-manager/app',
    'services/job-manager/tests',
    'services/downloader/app',
    'services/downloader/tests',
    'services/transcriber/app',
    'services/transcriber/tests',
    'services/storage/app',
    'services/storage/tests',
    'services/notifier/app',
    'services/notifier/tests',
    'services/admin/app',
    'services/admin/tests',
    'shared/models',
    'shared/events',
    'shared/utils',
    'shared/exceptions',
    'infra/docker',
    'infra/kubernetes',
    'infra/monitoring',
    'infra/backup',
    'infra/terraform',
    'tests/e2e',
    'tests/load',
    'tests/fixtures',
    'tests/contracts',
    'docs/diagrams',
    '.github/workflows'
)

foreach($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path "projeto_v2/$dir"
}
```

### Passo 2: Criar arquivos de configuração

```bash
# .gitignore
echo """
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
.pytest_cache/
.coverage
htmlcov/
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/
.vscode/
.idea/
*.swp
.DS_Store
""" > projeto_v2/.gitignore

# VERSION
echo "2.0.0" > projeto_v2/VERSION

# .env.example
cat > projeto_v2/.env.example << 'EOF'
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ytcaption
DATABASE_POOL_SIZE=10

# RabbitMQ
RABBITMQ_URL=amqp://user:password@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0

# Storage (MinIO)
MINIO_URL=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Logging
LOG_LEVEL=INFO

# Monitoring
PROMETHEUS_ENDPOINT=http://localhost:9090
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831

# JWT
JWT_SECRET=your-secret-key-change-in-prod
JWT_ALGORITHM=HS256

# YouTube API
YOUTUBE_API_KEY=your-api-key

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EOF
```

### Passo 3: Criar Makefile (atalhos úteis)

```bash
cat > projeto_v2/Makefile << 'EOF'
.PHONY: help up down logs test lint format clean

help:
	@echo "Available commands:"
	@echo "  make up              - Start docker-compose"
	@echo "  make down            - Stop docker-compose"
	@echo "  make logs            - Show logs"
	@echo "  make test            - Run unit tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-e2e        - Run E2E tests"
	@echo "  make test-coverage   - Run with coverage"
	@echo "  make lint            - Run linters"
	@echo "  make format          - Format code"
	@echo "  make clean           - Clean cache/temp files"

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	pytest services/*/tests/ -v --tb=short

test-integration:
	pytest services/*/tests/ -v -m integration

test-e2e:
	pytest tests/e2e/ -v -m e2e

test-coverage:
	pytest services/*/tests/ -v --cov=services/ --cov-report=html

lint:
	pylint services/*/app/
	flake8 services/*/app/

format:
	black services/
	isort services/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ htmlcov/ .coverage

EOF
```

### Passo 4: Criar requirements-base.txt

```bash
cat > projeto_v2/requirements-base.txt << 'EOF'
# Core
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.4.2
pydantic-settings==2.0.3

# Database
sqlalchemy==2.0.23
psycopg[binary]==3.13.0
alembic==1.12.1

# Message Queue
pika==1.3.2
aio-pika==9.1.1

# Redis
redis==5.0.0
hiredis==2.2.3

# HTTP Client
httpx==0.25.0
requests==2.31.0

# Circuit Breaker
pybreaker==1.3.0

# Monitoring
prometheus-client==0.18.0
jaeger-client==4.8.0
opentelemetry-api==1.20.0
opentelemetry-sdk==1.20.0
opentelemetry-instrumentation-fastapi==0.41b0
opentelemetry-exporter-jaeger==1.20.0

# Logging
python-json-logger==2.0.7

# Utils
python-dotenv==1.0.0
pyyaml==6.0.1

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.0
EOF

# requirements-dev.txt
cat > projeto_v2/requirements-dev.txt << 'EOF'
-r requirements-base.txt

# Linting
pylint==3.0.2
flake8==6.1.0
black==23.11.0
isort==5.13.2

# Testing
locust==2.16.1

# Development
ipython==8.17.2
ipdb==0.13.13
EOF
```

---

## Próxima Ação

1. **Crie os diretórios** acima
2. **Crie os arquivos de config** (.gitignore, .env.example, etc)
3. **Leia ESPECIFICACAO_SERVICOS.md** para começar código
4. **Use CONFIGURACAO_RESILIENCIA.md** como referência
5. **Comece implementando API Gateway ou Job Manager**

---

## Checklist

```
□ Criei todos diretórios
□ Criei .gitignore
□ Criei .env.example
□ Criei Makefile
□ Criei requirements-base.txt e requirements-dev.txt
□ Criei VERSION file
□ Fiz git init e git add
□ Pronto para começar código!
```

---

**Próximo**: Escolha seu serviço (API Gateway recomendado primeiro) e comece a codificar!
