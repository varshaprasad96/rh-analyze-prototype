FROM vllm/vllm-openai:latest

# vLLM can be configured with --otlp-traces-endpoint, but the base image may not ship
# OpenTelemetry Python packages. Install the minimal set required by vLLM tracing.
RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc


