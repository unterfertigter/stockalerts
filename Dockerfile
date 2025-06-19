# Use official Python image
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y sendmail && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY stock_alert.py ./
COPY config.json ./

CMD ["python", "stock_alert.py"]
