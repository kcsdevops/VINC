# Dockerfile para Video/Spotify Downloader Web App
FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (cache layer)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY video_downloader.py .
COPY web_downloader.py .
COPY spotify_search.py .
COPY spotify_cache.py .
COPY populate_cache.py .
COPY templates/ templates/

# Criar diretório de downloads
RUN mkdir -p downloads/audio downloads/video downloads/spotify

# Expor porta do Flask
EXPOSE 5000

# Variáveis de ambiente
ENV FLASK_APP=web_downloader.py
ENV PYTHONUNBUFFERED=1

# Comando para iniciar o servidor
CMD ["python", "web_downloader.py"]
