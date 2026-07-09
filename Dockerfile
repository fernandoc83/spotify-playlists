FROM python:3.13-slim

WORKDIR /app

# deps primero para aprovechar la cache de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código
COPY analyzer.py playlists.py scheduler.py ./

# headless: nunca intenta abrir un navegador dentro del contenedor
ENV SPOTIPY_HEADLESS=1 \
    PYTHONUNBUFFERED=1

# corre el scheduler (que a su vez dispara playlists.py según DIA_SEMANA/HORA)
CMD ["python", "-u", "scheduler.py"]
