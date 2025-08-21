# Multi-stage Dockerfile for HA Log Debugger AI

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

LABEL maintainer="HA Log Debugger AI"
LABEL description="AI-powered Home Assistant log analysis and recommendations"

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Set up application directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY static/ ./static/

# Create data directory for SQLite database
RUN mkdir -p /data && chown appuser:appuser /data

# Switch to non-root user
USER appuser

# Make sure user's local packages are in PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# Environment variables with defaults
ENV MODEL_NAME="gpt-3.5-turbo" \
    TZ="UTC" \
    HA_CONFIG_PATH="/config" \
    LOG_LEVEL="INFO" \
    WEB_PORT="8080"

# Note: OPENAI_ENDPOINT_URL and OPENAI_API_KEY should be set at runtime for security

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${WEB_PORT}/api/health || exit 1

# Expose web interface port
EXPOSE 8080

# Run the application
CMD ["python", "-m", "src.main"]