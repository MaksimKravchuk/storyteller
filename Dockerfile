FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached layer — only re-runs when lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra openai --extra anthropic --no-install-project

# Copy application code
COPY . .

CMD ["uv", "run", "python", "run_server.py"]
