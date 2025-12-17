FROM golang:1.21 AS cagent-builder
WORKDIR /app

# Download cagent binary v1.9.9
RUN wget -O cagent https://github.com/docker/cagent/releases/download/v1.9.9/cagent-linux-amd64
RUN chmod +x cagent

FROM debian:12-slim
WORKDIR /app

# Install CA certificates for HTTPS
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy cagent binary
COPY --from=cagent-builder /app/cagent /cagent

# Copy agent configuration
COPY agent.yaml /config/agent.yaml

# Create writable directories for cagent data
RUN mkdir -p /tmp/.cagent && chmod 777 /tmp/.cagent

# Environment variables
ENV PORT=8080
ENV AGENT_CONFIG=/config/agent.yaml
ENV HOME=/tmp

# Expose API port
EXPOSE 8080

# Run cagent in API server mode with session DB in writable location
ENTRYPOINT ["/cagent", "api", "/config/agent.yaml", "--session-db", "/tmp/.cagent/session.db"]

