FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
# libgomp: OpenMP runtime needed by LightGBM (account scores)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY revops_ai ./revops_ai
COPY models ./models
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8100
HEALTHCHECK --interval=15s --timeout=5s --retries=6 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8100/health').status==200 else 1)"
CMD ["uvicorn", "revops_ai.main:app", "--host", "0.0.0.0", "--port", "8100"]
