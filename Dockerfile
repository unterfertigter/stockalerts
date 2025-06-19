# Use official Python image
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY stock_alert.py ./
COPY config.json ./

CMD ["python", "stock_alert.py"]
