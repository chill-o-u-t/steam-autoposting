FROM python:3.11-slim

# рабочая директория внутри контейнера
WORKDIR /app

# скопировать requirements и поставить зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# скопировать проект
COPY . .

# переменные окружения будут подтягиваться из .env
CMD ["python", "bot.py"]
