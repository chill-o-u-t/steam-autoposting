FROM selenium/standalone-chrome:latest

WORKDIR /app

# Ставим python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
