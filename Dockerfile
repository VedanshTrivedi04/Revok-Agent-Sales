FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
WORKDIR /app
COPY revops-agent/apps/api/pyproject.toml revops-agent/apps/api/uv.lock revops-agent/apps/api/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY revops-agent/apps/api/ .
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENTRYPOINT ["sh", "scripts/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-4} --proxy-headers --forwarded-allow-ips '*'"]
