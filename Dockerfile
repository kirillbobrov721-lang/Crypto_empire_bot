FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir python-telegram-bot==13.15

# Копируем бота
COPY bot.py .

# Запускаем бота
CMD ["python", "bot.py"]
