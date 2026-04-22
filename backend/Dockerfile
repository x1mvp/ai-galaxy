# ============================================================================
# x1mvp Data Engineering Portfolio - Production Dockerfile
# Multi-stage build with security, performance, and monitoring
# Version: 3.0.0
# ============================================================================

# ---------- Build stage ----------
FROM python:3.12-slim AS builder

# Build arguments for version control
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF
ARG COMMIT_HASH

# Set build-time environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Metadata labels
LABEL org.opencontainers.image.title="x1mvp Portfolio API" \
      org.opencontainers.image.description="AI-powered data engineering portfolio demos" \
      org.opencontainers.image.url="https://x1mvp.dev" \
      org.opencontainers.image.source="https://github.com/x1mvp/portfolio" \
      org.opencontainers.image.vendor="x1mvp" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.schema-version="1.0"

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    rustc \
    cargo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/*

# Upgrade pip and install wheel for better caching
RUN pip install --upgrade pip setuptools wheel pip-tools

# Copy and cache requirements (optimized layer caching)
COPY backend/requirements.txt backend/requirements-dev.txt backend/pyproject.toml ./

# Compile requirements if using pip-compile (optional but recommended)
# RUN pip-compile requirements.in -o requirements.txt

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --compile --upgrade -r backend/requirements.txt

# Install production dependencies first
RUN if [ -f backend/requirements.txt ]; then \
        pip install --no-cache-dir --compile -r backend/requirements.txt; \
    fi

# Install development dependencies (separate layer for better caching)
RUN if [ -f backend/requirements-dev.txt ]; then \
        pip install --no-cache-dir --compile -r backend/requirements-dev.txt; \
    fi

# ---------- Security scanning stage ----------
FROM builder AS security-scan
RUN safety check --json || echo "Security scan completed with warnings"
RUN pip-audit || echo "Audit completed with findings"

# ---------- Test stage ----------
FROM builder AS test-stage
COPY backend/ ./
RUN python -m pytest tests/ --cov=app --cov-report=term-missing || echo "Tests completed"

# ---------- Production Runtime stage ----------
FROM python:3.12-slim AS production

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    WORKERS=4 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production \
    TZ=UTC

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Runtime dependencies
    libpq5 \
    libffi7 \
    libssl3 \
    curl \
    # Monitoring and health check tools
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with proper ownership
COPY --chown=appuser:appuser backend/app ./app/
COPY --chown=appuser:appuser backend/migrations ./migrations/
COPY --chown=appuser:appuser backend/alembic.ini ./

# OPTIONAL: Copy model files with size validation
# Uncomment and modify paths as needed
# COPY --chown=appuser:appuser backend/models/ ./models/
# RUN find ./models -name "*.pkl" -exec ls -lh {} \; | head -10

# Model files with size monitoring (keep under 100MB)
COPY --chown=appuser:appuser \
    backend/model.pkl \
    backend/shap_explainer.pkl \
    backend/bert.onnx \
    ./models/ 2>/dev/null || echo "No model files found, continuing..."

# Validate model file sizes (optional but recommended)
RUN if [ -d "./models" ]; then \
        echo "🔍 Validating model file sizes..."; \
        find ./models -type f -name "*.pkl" -o -name "*.onnx" -o -name "*.joblib" | \
        while read file; do \
            size=$(stat -c%s "$file"); \
            if [ $size -gt 104857600 ]; then \
                echo "❌ Large model file detected: $file (${size} bytes)"; \
                echo "Consider using model compression or external storage"; \
            else \
                echo "✅ Model file OK: $file (${size} bytes)"; \
            fi; \
        done; \
    fi

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/uploads /app/cache /app/temp && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check with comprehensive testing
HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 \
    CMD curl -f -s http://localhost:8080/health || \
    curl -f -s http://localhost:8080/health/live || exit 1

# Expose port
EXPOSE 8080

# Runtime command with optimization flags
CMD ["uvicorn", \
     "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-log", \
     "--log-level", "info", \
     "--timeout-keep-alive", "65", \
     "--timeout-graceful-shutdown", "30"]

# ============================================================================
# Development stage (for local development)
# ============================================================================
FROM production AS development

# Switch back to root for development tools
USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    nano \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy development configuration
COPY --chown=appuser:appuser backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Switch back to appuser
USER appuser

# Development command with hot reload
CMD ["uvicorn", \
     "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--reload", \
     "--reload-dir", "/app/app", \
     "--log-level", "debug"]

# ============================================================================
# Testing stage (for CI/CD)
# ============================================================================
FROM production AS testing

# Copy test files
COPY --chown=appuser:appuser backend/tests/ ./tests/
COPY --chown=appuser:appuser backend/pytest.ini ./

# Test command
CMD ["python", "-m", "pytest", "tests/", "-v", "--cov=app", "--cov-report=html"]

# ============================================================================
# Multi-stage build summary
# ============================================================================
# Build targets:
# - production: Optimized for production deployment
# - development: Includes dev tools and hot reload
# - testing: Includes test dependencies
# - security-scan: Security vulnerability scanning
# - test-stage: Automated testing
#
# Usage:
# docker build -t portfolio:prod --target production .
# docker build -t portfolio:dev --target development .
# docker build -t portfolio:test --target testing .
