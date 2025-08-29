FROM aivzbo/undetected-chromedriver:latest

# Опционально: делаем шелл "строже"
SHELL ["/bin/sh", "-exo", "pipefail", "-c"]

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Ставим Python и pip (в Alpine это отдельные пакеты)
RUN apk add --no-cache python3 py3-pip

# Создаём отдельный venv и сразу обновляем pip
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip

# Делаем venv системным по умолчанию для следующих слоёв/команд
ENV PATH="/opt/venv/bin:${PATH}"

# Если есть нативные зависимости (например, для psycopg2, lxml и т.п.),
# раскомментируйте следующую строку:
# RUN apk add --no-cache build-base musl-dev libffi-dev openssl-dev

# Устанавливаем зависимости ПЕРЕД копированием всего кода — так кэш лучше работает
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники
COPY . .

# Запуск через python из venv (он в PATH)
ENTRYPOINT ["python", "bot.py"]
