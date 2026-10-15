# Stage 1: Install dependencies with Poetry
FROM python:3.10-slim AS builder

# Environment settings
ENV POETRY_VERSION=1.8.3 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install git, Poetry and tomli (needed by toml_deps.py before the venv exists)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && pip install --no-cache-dir poetry==$POETRY_VERSION tomli==2.2.1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependencies first to cache them.
COPY pyproject.toml ./
COPY scripts/toml_deps.py ./scripts/toml_deps.py
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY .env-test .env

ARG CONTAINER_GITHUB_PAT

# Rewrite dependencies before creating the venv so the system Python can use tomli.
RUN if [ -n "${CONTAINER_GITHUB_PAT}" ]; then \
        git config --global url."https://x-access-token:${CONTAINER_GITHUB_PAT}@github.com/".insteadOf "https://github.com/"; \
    fi \
    && CONTAINER_GITHUB_PAT=${CONTAINER_GITHUB_PAT} /usr/local/bin/python scripts/toml_deps.py pyproject.toml /deps/exports \
    && python -m venv .venv \
    && poetry lock \
    && poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Final lightweight image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /app /app


# Expose the application on port 8000
EXPOSE 8000

# Start the uvicorn
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
