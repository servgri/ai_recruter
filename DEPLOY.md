# Деплой на Render.com

## Быстрый старт

1. Подключите репозиторий к [Render](https://render.com).
2. Создайте **Web Service**, выберите репозиторий.
3. Настройки:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -k eventlet -w 1 --timeout 180 -b 0.0.0.0:$PORT wsgi:app`
4. В **Environment** добавьте переменные (при необходимости):
   - `SECRET_KEY` — случайная строка (можно сгенерировать в Render).
   - `DATABASE_PATH` — путь к SQLite (по умолчанию `data.db`; на бесплатном плане данные не сохраняются между деплоями).
   - Остальные переменные из `services/config.py` (Hugging Face, эталоны, метод эмбеддингов и т.д.) — по необходимости.
5. Деплой.

Либо используйте **Blueprint**: в корне репозитория есть `render.yaml` — при создании сервиса через Blueprint Render подхватит команды сборки и запуска из него.

## Важно

- **Порт:** Render задаёт переменную `PORT`; Gunicorn использует её автоматически, менять ничего не нужно.
- **WebSockets:** Запуск через `gunicorn -k eventlet -w 1` обеспечивает работу Flask-SocketIO (один воркер).
- **База данных:** По умолчанию используется SQLite в файле `data.db`. На бесплатном плане файловая система эфемерная — после перезапуска/редиплоя данные могут пропадать. Для сохранения данных используйте Render Disk (платный план) и задайте `DATABASE_PATH` в путь на диске.
- **PDF-экспорт:** На Render обычно работает fallback на xhtml2pdf (WeasyPrint требует системных библиотек и может быть недоступен).

## Переменные окружения (опционально)

| Переменная | Описание |
|------------|----------|
| `SECRET_KEY` | Секрет Flask (обязательно сменить в продакшене) |
| `DATABASE_PATH` | Путь к файлу SQLite |
| `EMBEDDING_METHOD` | `sbert` или `qwen` |
| `API_PRIORITY` | `api_first` или `local_first` |
| `HF_API_TOKEN` | Токен Hugging Face API |
| `ETALON_HR_JSON`, `ETALON_AI_JSON` | Пути к JSON эталонов (HR/AI) |
| `LLM_LIKELIHOOD_METHOD` | `heuristic` или `bertscore` |
| `BERTSCORE_MODEL` | Модель для BERT-score (например `cointegrated/rubert-tiny2`) |

Полный список — в `services/config.py`.
