# The build context is the repository root (see image_build_context in the
# Wrangler configs), not infra/cloudflare/gateway.  Pin the Rust toolchain so
# the edition 2024 / rust-version 1.85 extension cannot silently build with an
# older distribution package.
FROM python:3.12-slim-bookworm AS builder

ARG RUST_VERSION=1.85.1
ENV CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    PATH=/opt/cargo/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        ca-certificates \
        curl \
        pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --proto '=https' --tlsv1.2 --silent --show-error https://sh.rustup.rs \
        | sh -s -- -y --profile minimal --default-toolchain "${RUST_VERSION}" \
    && rustc --version \
    && cargo --version

COPY pyproject.toml uv.lock ./
COPY backend ./backend
COPY rust ./rust
RUN pip install --no-cache-dir uv==0.11.26 \
    && uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
RUN useradd --create-home --uid 10001 appuser

# Provider credentials, JWT keys, database DSNs, and other runtime secrets are
# never copied into the image.  The Worker injects SCHEMASPRINT_* bindings when
# it starts this private container.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend /app/backend
COPY --from=builder /app/pyproject.toml /app/uv.lock /app/
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "schemasprint_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
