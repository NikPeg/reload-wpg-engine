# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r wpgbot && useradd -r -g wpgbot wpgbot

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create app directory and set ownership
WORKDIR /app
RUN chown -R wpgbot:wpgbot /app

# Copy application code
COPY --chown=wpgbot:wpgbot . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs && \
    chown -R wpgbot:wpgbot /app/data /app/logs

# Switch to non-root user
USER wpgbot

# Expose port (if needed for webhooks)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from wpg_engine.models import get_db; asyncio.run(next(get_db()).__anext__())" || exit 1

# Default command
CMD ["python", "main.py"]