# Tasqueue Python Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY tasqueue/ ./tasqueue/
COPY examples/ ./examples/
COPY config.yaml .

# Create non-root user
RUN useradd -m -u 1000 tasqueue && \
    chown -R tasqueue:tasqueue /app

# Switch to non-root user
USER tasqueue

# Set Python path
ENV PYTHONPATH=/app

# Default command (can be overridden)
CMD ["python", "-m", "tasqueue"]
