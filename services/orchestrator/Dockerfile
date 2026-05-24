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
COPY services/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY services/orchestrator/ .

# Cria diretórios esperados pela aplicação
RUN mkdir -p /app/logs /app/artifacts

# Expõe porta
EXPOSE 8000

# Comando para iniciar
CMD ["python", "run.py"]
