# Инструкция по использованию

## Запуск Flask сервиса

```bash
python app.py
```

Сервис будет доступен по адресу: `http://localhost:5000`

## Загрузка файлов

### Загрузка одного файла

```bash
python upload_files.py data/51.txt
```

### Загрузка всех файлов из папки

```bash
python upload_files.py data/
```

### Загрузка с указанием сервера

```bash
python upload_files.py data/ --server http://localhost:5000
```

### Загрузка только определенных форматов

```bash
python upload_files.py data/ --extensions .txt .pdf
```

## Экспорт в CSV

### Стандартный формат (один файл = одна строка)

```bash
python export_to_csv.py
```

### Детальный формат (каждое задание = отдельная строка)

```bash
python export_to_csv.py --detailed
```

### Указание папки и выходного файла

```bash
python export_to_csv.py --input-dir data_loaded --output results.csv
```

## Использование через API

### Загрузка файла через curl

```bash
curl -X POST -F "file=@data/51.txt" http://localhost:5000/upload
```

### Экспорт CSV через API

```bash
# Стандартный формат
curl http://localhost:5000/export/csv -o exported_data.csv

# Детальный формат
curl "http://localhost:5000/export/csv?detailed=true" -o exported_data_detailed.csv
```

## Формат CSV

### Стандартный формат содержит:
- filename - имя файла
- file_type - тип файла
- parsed_at - дата обработки
- task_1, task_2, task_3, task_4 - содержимое заданий
- full_content - полный текст файла

### Детальный формат содержит:
- filename - имя файла
- file_type - тип файла
- parsed_at - дата обработки
- task_number - номер задания
- task_content - содержимое задания
