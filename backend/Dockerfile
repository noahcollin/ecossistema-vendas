FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    TZ=America/Sao_Paulo \
    HOME=/tmp \
    UV_CACHE_DIR=/tmp/.uv-cache \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv && \
    addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev || uv sync

COPY . .
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
