FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data
EXPOSE 8181

ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/cars.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8181"]