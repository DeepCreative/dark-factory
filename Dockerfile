FROM python:3.11-slim AS base

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

COPY requirements.txt requirements-service.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-service.txt

COPY dark_factory/ dark_factory/
COPY pyproject.toml ./

RUN pip install --no-cache-dir -e .

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "dark_factory.service.api:app", "--host", "0.0.0.0", "--port", "8080"]
