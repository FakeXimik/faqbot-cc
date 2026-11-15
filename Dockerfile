# Build:  docker build -t faqbot .
# Run:    docker run --rm -p 8000:8000 --env-file .env faqbot
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PORT=8000

WORKDIR /app

# Cache dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY static ./static

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"

# secrets from env
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 30 app:app"]
