FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY README.md ./README.md

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
