# Запуск в Docker

## Требования

- Docker и Docker Compose на сервере (или только `docker` для одиночного контейнера).
- Файл `.env` в корне проекта с переменными: `SECRET_KEY`, `HF_API_TOKEN` (и при необходимости `DATABASE_PATH`, `ETALON_HR_JSON`, `ETALON_AI_JSON` и др.). См. `ENV_KEYS.md` или `README.md`.

## Сборка и запуск через Docker Compose

```bash
# Сборка образа и запуск в фоне
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

Приложение будет доступно по адресу: `http://IP_СЕРВЕРА:5000`.

## Сборка и запуск без Compose

```bash
# Сборка образа
docker build -t ai_recruter .

# Запуск (подставьте путь к .env или задайте переменные вручную)
docker run -d --name ai_recruter_app -p 5000:5000 --env-file .env --restart unless-stopped \
  -v ai_recruter_data:/app/data \
  ai_recruter
```

Данные БД сохраняются в volume `ai_recruter_data`.

## Переменные окружения

Создайте `.env` в каталоге с проектом (рядом с `docker-compose.yml`). Минимум:

```env
SECRET_KEY=длинная_случайная_строка
HF_API_TOKEN=hf_ваш_токен
```

Остальные переменные — по необходимости (см. `services/config.py`).

## Nginx перед контейнером

Чтобы отдавать приложение по порту 80 и по домену, на хосте ставят nginx и проксируют запросы на `127.0.0.1:5000`. Конфиг nginx — как в инструкции по деплою на VPS (proxy_pass на 127.0.0.1:5000).
