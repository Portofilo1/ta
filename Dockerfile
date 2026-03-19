FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем папку для фото
RUN mkdir -p /app/photos

COPY . .

CMD ["python", "bot.py"]