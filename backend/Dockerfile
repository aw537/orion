FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

RUN mkdir -p /app/data

RUN addgroup --system orion && adduser --system --ingroup orion orion \
    && chown -R orion:orion /app
USER orion

EXPOSE 8000 8787

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
