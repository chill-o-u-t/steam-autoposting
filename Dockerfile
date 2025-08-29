FROM python:3.11-slim

# Установим Chrome и необходимые зависимости
RUN apt-get update && apt-get install -y \
    wget unzip xvfb libnss3 libxss1 libappindicator3-1 libatk-bridge2.0-0 libgtk-3-0 \
    fonts-liberation libasound2 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxrandr2 libgbm1 libpango1.0-0 libatk1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Установим Chrome
RUN wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb

# Установим pip-зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Создаём папку для логов
RUN mkdir logs

# Запуск бота
CMD ["python", "bot_selenium.py"]
