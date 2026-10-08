FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# 数据与报告持久化目录
VOLUME ["/data", "/reports"]

EXPOSE 7878

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:7878", "app.main:app"]
