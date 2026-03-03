# AI Recruiter — образ для деплоя (Flask + gunicorn + eventlet)
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для сборки пакетов и работы библиотек
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала PyTorch (CPU), чтобы не тянуть CUDA-зависимости
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Зависимости приложения
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY app.py wsgi.py ./
COPY parsers/ ./parsers/
COPY extractors/ ./extractors/
COPY services/ ./services/
COPY utils/ ./utils/
COPY templates/ ./templates/
COPY static/ ./static/

# Каталоги для данных (БД, модели, логи) — при запуске можно монтировать volume
RUN mkdir -p /app/data /app/models /app/logs

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/data.db

EXPOSE 5000

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "--timeout", "180", "-b", "0.0.0.0:5000", "wsgi:app"]
