FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including libpq for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy monorepo requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source trees
COPY packages/ ./packages/
COPY services/ ./services/
COPY pyproject.toml ./

# Install monorepo in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV PYTHONPATH=/app

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
