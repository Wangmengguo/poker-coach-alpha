# Poker Coach Alpha - Production Dockerfile
# 
# Build: docker build -t poker-coach .
# Run:   docker run -p 8010:8010 -v ./data:/app/data poker-coach

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any compiled packages are needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

# Expose the application port
EXPOSE 8010

# Environment variables (can be overridden at runtime)
ENV APP_PREFIX=/cards
ENV AI_PROVIDER=openai
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/cards/')" || exit 1

# Run the application
# IMPORTANT: --workers 1 is required because game state is in memory
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]
