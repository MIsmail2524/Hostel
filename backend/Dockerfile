# Kamra API + reconstruction worker image
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY seed.py .
# Run as an unprivileged user
RUN useradd --create-home --uid 10001 kamra && mkdir -p /data/storage && chown -R kamra /data
USER kamra
ENV KAMRA_STORAGE_DIR=/data/storage
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8090/healthz')"
# Only trust X-Forwarded-For from your reverse proxy (set FORWARDED_ALLOW_IPS to its IP/CIDR).
ENV FORWARDED_ALLOW_IPS=127.0.0.1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--proxy-headers", "--workers", "2"]
