FROM python:3.11-slim

# Force stdin/stdout/stderr to be unbuffered so logs flush immediately
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies (including pg_isready and postgresql-client for healthcheck/backup)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ /app/app/
COPY tests/ /app/tests/
COPY pytest.ini* /app/


# Expose FastAPI port
EXPOSE 8000

# Default cmd runs FastAPI. Can be overridden in compose to run arq worker or pytest.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
