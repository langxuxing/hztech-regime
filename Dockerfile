FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md ./
COPY algorithm ./algorithm
COPY ai_trade_advisor ./ai_trade_advisor

RUN pip install --no-cache-dir -e ".[dev]"

ENV DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/data/db /app/data/cache /app/data/logs

EXPOSE 8765

CMD ["python", "-m", "ai_trade_advisor.api_server", "--host", "0.0.0.0", "--port", "8765", "--skip-orderbook"]
