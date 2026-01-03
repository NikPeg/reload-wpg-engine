# Single-stage build for better compatibility
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r wpgbot && useradd -r -g wpgbot wpgbot

# Create app directory and set ownership
WORKDIR /app
RUN chown -R wpgbot:wpgbot /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY --chown=wpgbot:wpgbot . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs && \
    chown -R wpgbot:wpgbot /app/data /app/logs

# Switch to non-root user
USER wpgbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from wpg_engine.models import get_db; asyncio.run(get_db().__anext__())" || exit 1

# Default command
CMD ["python", "main.py"]