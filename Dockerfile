# ---------- Stage 1: build dependencies with Poetry ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.5.0 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --without dev

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN mkdir -p /app/data

CMD ["python", "-m", "bot.main"]
