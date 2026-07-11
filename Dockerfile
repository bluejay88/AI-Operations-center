FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ai_ops_center ./ai_ops_center
COPY config ./config
COPY sql ./sql

RUN pip install --no-cache-dir .

EXPOSE 8088

CMD ["uvicorn", "ai_ops_center.api:app", "--host", "0.0.0.0", "--port", "8088"]

