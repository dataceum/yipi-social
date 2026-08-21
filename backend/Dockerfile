# syntax=docker/dockerfile:1
#
# Multi-stage build for the Dataceum PaaS / Yipi Social FastAPI backend.
#
# Stage 1 (builder) resolves and installs dependencies with uv, using the
# project's own uv.lock so the image gets the exact versions you've been
# developing against — not whatever pip would re-resolve today.
#
# Stage 2 (runtime) copies only the built virtualenv + app code into a
# clean slim image, runs as a non-root user, and stays small enough to
# run comfortably on minimal ECS Fargate CPU/RAM (per README.md's stated
# reasoning for choosing FastAPI over Django here).

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first, separately from application code, so this
# (slow) layer stays cached across builds that only touch app/.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim AS runtime

# Postgres client libs for psycopg2-binary / asyncpg at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# Matches app/main.py's root_health_check() — point the ECS container
# health check and the ALB target group's health check path at "/".
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/').status==200 else 1)"

# Fargate scales by running more task copies, not more in-process workers,
# so a single-worker server per container is the right default here — see
# docs/AWS_DEPLOYMENT.md for how the ECS service's desired task count
# handles horizontal scaling instead.
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
