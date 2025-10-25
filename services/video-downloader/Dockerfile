# Use imagem Python slim mais leve
FROM python:3.11-slim

# Instala apenas curl para healthcheck (yt-dlp não precisa de ffmpeg para MP4 direto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Diretório de trabalho
WORKDIR /app

# Copia apenas requirements primeiro (aproveita cache de layers)
COPY requirements.txt .

# Instala dependências Python sem cache
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY app/ ./app/
COPY run.py .

# Cria diretório de cache com permissões
RUN mkdir -p /app/cache && chmod 755 /app/cache

# Usuário não-root para segurança
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expõe porta
EXPOSE 8000

# Comando padrão
CMD ["python", "run.py"]