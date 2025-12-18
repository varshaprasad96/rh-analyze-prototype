FROM registry.access.redhat.com/ubi9/ubi-minimal:latest AS cagent-builder
WORKDIR /app

# Install wget
RUN microdnf install -y wget && microdnf clean all

# Download cagent binary v1.9.9
RUN wget -O cagent https://github.com/docker/cagent/releases/download/v1.9.9/cagent-linux-amd64
RUN chmod +x cagent

FROM registry.access.redhat.com/ubi9/ubi-minimal:latest
WORKDIR /app

# Install CA certificates (already included in UBI)
RUN microdnf install -y ca-certificates && microdnf clean all

# Copy cagent binary
COPY --from=cagent-builder /app/cagent /cagent

# Copy agent configuration
COPY agent.yaml /config/agent.yaml

# Create writable directories for cagent data (UBI runs as non-root)
USER root
RUN mkdir -p /tmp/.cagent && chmod 777 /tmp/.cagent
USER 1001

# Environment variables
ENV PORT=8080
ENV AGENT_CONFIG=/config/agent.yaml
ENV HOME=/tmp

# Expose API port
EXPOSE 8080

# Run cagent in API server mode with session DB in writable location
ENTRYPOINT ["/cagent", "api", "/config/agent.yaml", "--session-db", "/tmp/.cagent/session.db"]

