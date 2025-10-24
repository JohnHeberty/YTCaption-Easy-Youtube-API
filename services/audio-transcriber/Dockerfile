# Use Python 3.11 slim (mais leve e moderno)
FROM python:3.11-slim

# Instala dependências do sistema para processamento de áudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Diretório de trabalho
WORKDIR /app

# Copia requirements
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY app/ ./app/
COPY run.py .

# Cria diretórios
RUN mkdir -p /app/uploads /app/processed && chmod 755 /app/uploads /app/processed

# Usuário não-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expõe porta
EXPOSE 8001

# Comando padrão
CMD ["python", "run.py"]
