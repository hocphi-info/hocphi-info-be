# Multi-stage build voi uv. Stage "build" co toolchain uv de cai deps; stage
# "runtime" chi copy .venv + code, chay bang user khong phai root.
#
# Tuong duong Go: build stage (co go toolchain) -> runtime distroless/alpine —
# owner da quen pattern nay tu Dockerfile Go cu.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Cai deps truoc — cache mount + tach khoi COPY code de khong invalidate cache
# moi lan sua code (chi invalidate khi pyproject.toml/uv.lock doi).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime
RUN groupadd -r app && useradd -r -g app -d /app app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
