# syntax=docker/dockerfile:1

FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_HOME=/opt/poetry \
    PATH="/opt/poetry/bin:${PATH}" \
    PYTHONPATH="/app" \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.0.1
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry --version

WORKDIR /app

# Install dependencies first (better layer caching)
COPY pyproject.toml poetry.lock* /app/
# Install only dependencies first to leverage Docker layer caching
RUN poetry install --no-interaction --no-ansi --no-root

# Copy app code
COPY app /app/app
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]


