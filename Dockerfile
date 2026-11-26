# BissBTC paper scanner + dashboard - Linux image for the VPS (README "Running on the VPS", docker-compose.yaml).
FROM python:3.12-slim

# the git commit this image was built from (set by the GitHub workflow); shown on the dashboard
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    TZ=UTC \
    DASHBOARD_BIND=0.0.0.0 \
    DASHBOARD_PORT=8030

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY biss biss
COPY config.yaml pytest.ini ./
COPY tests tests
RUN useradd --create-home --uid 1000 biss && mkdir -p /app/data && chown -R biss /app
USER biss

EXPOSE 8030
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8030/healthz', timeout=4)" || exit 1
# scanner in the main thread, dashboard in a background thread; state lives in /app/data (a volume)
CMD ["python", "-m", "biss.app"]
