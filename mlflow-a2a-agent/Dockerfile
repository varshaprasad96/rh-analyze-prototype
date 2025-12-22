# MLflow A2A Agent with Llama Stack
# Fully configurable via environment variables

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create non-root user
RUN useradd -m -u 1000 agent
USER agent

# Expose port
EXPOSE 8080

# Environment variables with defaults
ENV PORT=8080 \
    HOST=0.0.0.0 \
    AGENT_NAME="MLflow A2A Agent" \
    AGENT_DESCRIPTION="An AI agent powered by Llama Stack" \
    AGENT_VERSION="1.0.0" \
    LLAMASTACK_URL="http://localhost:8321" \
    LLAMASTACK_MODEL="meta-llama/Llama-3.2-3B-Instruct" \
    SYSTEM_PROMPT="You are a helpful AI assistant." \
    RAG_ENABLED="false" \
    VECTOR_STORE_IDS="" \
    MCP_SERVERS_JSON="[]" \
    MLFLOW_TRACKING_URI="" \
    SKILLS_JSON='[{"id":"answer","name":"Answer Questions","description":"Answer user questions"}]'

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the server
CMD ["python", "server.py"]

