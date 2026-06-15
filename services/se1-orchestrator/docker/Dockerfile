FROM python:3.11-slim

# Define o nome do serviço como variável de ambiente
ENV SERVICE_NAME=orchestrator
ENV PYTHONPATH=/app

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia shared library como common/ (build context é raiz do projeto)
COPY shared/ /app/common/

# Copia requirements e instala dependências Python
COPY services/se1-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação (exceto common/ que é symlink, já copiado acima)
COPY services/se1-orchestrator/run.py .
COPY services/se1-orchestrator/main.py .
COPY services/se1-orchestrator/core/ ./core/
COPY services/se1-orchestrator/domain/ ./domain/
COPY services/se1-orchestrator/infrastructure/ ./infrastructure/
COPY services/se1-orchestrator/modules/ ./modules/
COPY services/se1-orchestrator/services/ ./services/
COPY services/se1-orchestrator/orchestrator/ ./orchestrator/
COPY services/se1-orchestrator/api/ ./api/

# Cria diretórios esperados pela aplicação
RUN mkdir -p /app/logs /app/artifacts

# Expõe porta
EXPOSE 8000

# Comando para iniciar
CMD ["python", "run.py"]
