FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    scikit-learn \
    fastapi \
    uvicorn \
    pydantic

# Copy application code
COPY pipeline.py serve.py monitor.py ./

# Train model at build time
RUN python pipeline.py

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run serving
CMD ["python", "serve.py"]
