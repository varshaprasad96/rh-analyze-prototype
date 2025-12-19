FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Expose MCP server port
EXPOSE 8080

# Run the FastMCP server - use streamable-http for kagent compatibility
ENTRYPOINT ["fastmcp", "run", "server.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080"]
