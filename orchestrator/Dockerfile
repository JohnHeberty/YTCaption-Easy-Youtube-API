FROM python:3.11-slim

# Define o nome do serviço como variável de ambiente
ENV SERVICE_NAME=orchestrator
ENV PYTHONPATH=/app

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia biblioteca common (local copy in service directory)
COPY common/ /app/common/

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Cria diretórios esperados pela aplicação
RUN mkdir -p /app/logs /app/artifacts

# Expõe porta
EXPOSE 8000

# Comando para iniciar
CMD ["python", "run.py"]
