# Single backend image, used for three roles by docker-compose (one build, one
# artifact): the API (uvicorn), the Celery worker, and the one-shot migrate job.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code + Alembic config (migrations live in app/database/migrations).
COPY alembic.ini .
COPY start.sh .
COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness: the orchestrator restarts the container if /health stops responding.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# uvicorn handles SIGTERM gracefully (drains in-flight requests) for clean deploys.
# Shell form honors $PORT (Render/Fly/Cloud Run inject it); defaults to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
