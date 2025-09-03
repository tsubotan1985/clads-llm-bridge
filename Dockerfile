# Multi-stage build for production
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements and install Python dependencies directly
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Make sure scripts are usable
ENV PATH=/root/.local/bin:$PATH

# Environment variables with defaults
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV WEB_UI_PORT=4322
ENV PROXY_PORT=4321
ENV DATABASE_PATH=/app/data/clads_llm_bridge.db
ENV DATA_DIR=/app/data
ENV INITIAL_PASSWORD=Hakodate4

# Python environment optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create data directory and set permissions
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy application code
COPY src/ ./src/
COPY *.py ./

# Keep as root user for now to avoid permission issues
# USER appuser

# Expose ports for Web UI (4322) and Proxy (4321)
EXPOSE 4321 4322

# Health check endpoint - check both services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${WEB_UI_PORT}/health && \
        curl -f http://localhost:${PROXY_PORT}/health || exit 1

# Run the application
CMD ["python3", "main.py"]