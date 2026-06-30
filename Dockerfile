# Build Stage
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    AETHERSYNC_DB_PATH=/app/data/aethersync.db \
    AETHERSYNC_VAULT_DIR=/app/data/shared_vault

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create a directory for persistent data and configure permissions for non-root containers
RUN mkdir -p /app/data && chmod -R 777 /app/data

# Expose port
EXPOSE 7860

# Start command
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips '*'"]
