FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/model-cache

WORKDIR /app

RUN addgroup --system stockpulse \
    && adduser --system --ingroup stockpulse --home /app stockpulse

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[ai,postgres]" \
    && python -m stockpulse.model_cache \
    && mkdir -p /app/data/raw /app/model-cache \
    && chown -R stockpulse:stockpulse /app

USER stockpulse

CMD ["stockpulse", "--daily-pipeline"]
