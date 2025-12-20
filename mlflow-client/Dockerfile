# Dockerfile for MLflow Agent Logger
# This image includes the Llamastack agent wrapper and logging script
# Built on top of the official MLflow image

FROM ghcr.io/mlflow/mlflow:latest

# Install required Python packages
RUN pip install --no-cache-dir openai pydantic>=2.0.0 boto3

# Create workspace directory
WORKDIR /workspace

# Copy agent wrapper and logging script
COPY llamastack_agent_wrapper_direct.py /workspace/
COPY log_llamastack_agent_direct.py /workspace/

# Set default environment variables (can be overridden at runtime)
ENV MLFLOW_TRACKING_URI="http://mlflow.rh-analyze.svc.cluster.local:5000"
ENV LLAMASTACK_BASE_URL="http://llamastack-with-userconfig-service.rh-analyze.svc.cluster.local:8321"
ENV LLAMASTACK_AGENT_ID="ollama/llama3.2:1b"
ENV LLAMASTACK_API_KEY="fake"
ENV MLFLOW_EXPERIMENT="llamastack-agent-wrapper-direct"
ENV MLFLOW_MODEL_NAME="llamastack-agent-wrapper-direct"

# Default command runs the logging script
CMD ["python", "/workspace/log_llamastack_agent_direct.py"]

