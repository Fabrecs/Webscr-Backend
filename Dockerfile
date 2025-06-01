# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set default scraping configuration (can be overridden via environment variables)
ENV SCRAPING_ENABLED=true \
    SCRAPING_MAX_RETRIES=3 \
    SCRAPING_BASE_TIMEOUT=20 \
    SCRAPING_RETRY_DELAY_MIN=0.5 \
    SCRAPING_RETRY_DELAY_MAX=2 \
    CIRCUIT_BREAKER_FAILURE_THRESHOLD=5 \
    CIRCUIT_BREAKER_TIMEOUT_DURATION=300

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check that doesn't rely on external ML API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 