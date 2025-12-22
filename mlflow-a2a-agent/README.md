# MLflow A2A Agent

A fully configurable AI agent that combines:
- **Llama Stack** for LLM inference and RAG
- **MLflow ResponsesAgent** for automatic tracing
- **A2A Protocol** for agent discovery and communication
- **Generic MCP integration** for extensible tool support

## Features

- **A2A Protocol Compliant**: Discoverable via `/.well-known/agent.json`
- **Fully Configurable**: All settings via environment variables
- **Generic MCP Support**: Configure any number of MCP servers via JSON
- **RAG Built-in**: Native Llama Stack RAG via `builtin::rag` toolgroup
- **MLflow Tracing**: Automatic tracing of all agent interactions
- **Kubernetes Native**: Ready for kagenti deployment

## Quick Start

### Local Development

```bash
# Set required environment variables
export LLAMASTACK_URL="http://localhost:8321"
export LLAMASTACK_MODEL="meta-llama/Llama-3.2-3B-Instruct"
export SYSTEM_PROMPT="You are a helpful assistant."

# Optional: Enable RAG
export RAG_ENABLED="true"
export VECTOR_STORE_IDS="my-vector-store"

# Optional: Configure MCP servers
export MCP_SERVERS_JSON='[{"name":"github","url":"http://localhost:8080/mcp","headers":{"Authorization":"Bearer ${GITHUB_TOKEN}"}}]'
export GITHUB_TOKEN="ghp_xxx"

# Run the server
python server.py
```

### Build Docker Image

```bash
# Build locally
docker build -t mlflow-a2a-agent:latest .

# Or use the Makefile target
make build-mlflow-a2a-agent
```

### Deploy to Kubernetes (kagenti)

```bash
# 1. Update namespace in deployment files
NAMESPACE=your-namespace
sed -i "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" deployment.yaml secret.yaml

# 2. Create secrets (update with real tokens first!)
kubectl apply -f secret.yaml

# 3. Build and push image to OpenShift registry
oc project $NAMESPACE
docker build -t image-registry.openshift-image-registry.svc:5000/$NAMESPACE/mlflow-a2a-agent:latest .
docker push image-registry.openshift-image-registry.svc:5000/$NAMESPACE/mlflow-a2a-agent:latest

# 4. Deploy the agent
kubectl apply -f deployment.yaml

# Or use the Makefile targets
make deploy-mlflow-a2a-agent
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT_NAME` | No | "MLflow A2A Agent" | Display name for A2A discovery |
| `AGENT_DESCRIPTION` | No | "An AI agent..." | Description for A2A discovery |
| `AGENT_VERSION` | No | "1.0.0" | Version for A2A discovery |
| `LLAMASTACK_URL` | Yes | http://localhost:8321 | Llama Stack server URL |
| `LLAMASTACK_MODEL` | Yes | meta-llama/Llama-3.2-3B-Instruct | Model identifier |
| `SYSTEM_PROMPT` | No | "You are a helpful..." | Agent instructions |
| `RAG_ENABLED` | No | "false" | Enable RAG tool |
| `VECTOR_STORE_IDS` | No | "" | Comma-separated vector DB IDs |
| `MCP_SERVERS_JSON` | No | "[]" | JSON array of MCP server configs |
| `MLFLOW_TRACKING_URI` | No | "" | MLflow tracking server URL |
| `SKILLS_JSON` | No | (default skills) | A2A skills definition |
| `PORT` | No | 8080 | Server port |

### MCP Server Configuration

The `MCP_SERVERS_JSON` environment variable accepts a JSON array of server configurations:

```json
[
  {
    "name": "github",
    "url": "http://github-mcp:8080/mcp",
    "transport": "streamable-http",
    "headers": {
      "Authorization": "Bearer ${GITHUB_TOKEN}"
    },
    "tools": ["get_file_contents", "search_code"]
  },
  {
    "name": "slack",
    "url": "http://slack-mcp:8080/mcp",
    "headers": {
      "Authorization": "Bearer ${SLACK_TOKEN}"
    }
  }
]
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Server identifier (used in tool names) |
| `url` | Yes | MCP server endpoint URL |
| `transport` | No | "streamable-http" (default) or "sse" |
| `headers` | No | HTTP headers (supports `${ENV_VAR}` substitution) |
| `tools` | No | Tool whitelist (empty = all tools) |

### Token Substitution

Header values support `${VAR_NAME}` syntax for secure token injection:

```yaml
env:
  - name: GITHUB_TOKEN
    valueFrom:
      secretKeyRef:
        name: mcp-tokens
        key: github-token
  - name: MCP_SERVERS_JSON
    value: '[{"name":"github","url":"...","headers":{"Authorization":"Bearer ${GITHUB_TOKEN}"}}]'
```

## API Endpoints

### A2A Discovery

```
GET /.well-known/agent.json
```

Returns the A2A Agent Card for discovery.

### JSON-RPC

```
POST /
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Hello, how can you help?"}]
    }
  },
  "id": 1
}
```

**Supported Methods:**

- `tasks/send` - Submit a task to the agent
- `tasks/get` - Get task status and results
- `tasks/cancel` - Cancel a running task

### Health Checks

```
GET /health  # Liveness probe
GET /ready   # Readiness probe
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kagenti Agent CR                          │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │ Env Variables   │ │ MCP_SERVERS_JSON│ │ K8s Secrets   │ │
│  └────────┬────────┘ └────────┬────────┘ └───────┬───────┘ │
└───────────┼────────────────────┼──────────────────┼─────────┘
            │                    │                  │
            ▼                    ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Pod                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FastAPI Server (:8080)                  │   │
│  │  ┌─────────────────┐  ┌─────────────────────────┐  │   │
│  │  │ /.well-known/   │  │ / (JSON-RPC)            │  │   │
│  │  │ agent.json      │  │ - tasks/send            │  │   │
│  │  └─────────────────┘  │ - tasks/get             │  │   │
│  │                       └───────────┬─────────────┘  │   │
│  └───────────────────────────────────┼────────────────┘   │
│                                      │                     │
│  ┌───────────────────────────────────▼────────────────┐   │
│  │           MLflow ResponsesAgent Wrapper            │   │
│  │  ┌───────────────────────────────────────────┐    │   │
│  │  │        llama_stack_client.Agent           │    │   │
│  │  │  - Session management                     │    │   │
│  │  │  - Streaming turns                        │    │   │
│  │  │  - Tool execution                         │    │   │
│  │  └───────────────────────────────────────────┘    │   │
│  └────────────────────┬───────────────────────────────┘   │
│                       │                                    │
│  ┌────────────────────▼───────────────────────────────┐   │
│  │           MCP ClientTool Wrappers                  │   │
│  │  - Dynamic tool discovery                          │   │
│  │  - Token substitution                              │   │
│  │  - HTTP calls to MCP servers                       │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
            │                    │                  │
            ▼                    ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │ Llama Stack   │  │ MCP Servers   │  │ MLflow        │
    │ - Inference   │  │ - GitHub      │  │ Tracking      │
    │ - RAG         │  │ - Slack       │  │               │
    │ - Vector DBs  │  │ - etc.        │  │               │
    └───────────────┘  └───────────────┘  └───────────────┘
```

## Files

```
mlflow-a2a-agent/
├── Dockerfile          # Container image definition
├── requirements.txt    # Python dependencies
├── server.py           # FastAPI A2A server
├── agent_wrapper.py    # MLflow ResponsesAgent wrapper
├── mcp_tools.py        # Dynamic MCP tool registration
├── deployment.yaml     # Kagenti Agent CR
├── secret.yaml         # MCP tokens secret
└── README.md           # This file
```

## Development

### Testing Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run with minimal config
export LLAMASTACK_URL="http://localhost:8321"
python server.py

# Test A2A discovery
curl http://localhost:8080/.well-known/agent.json

# Test JSON-RPC
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tasks/send","params":{"message":{"role":"user","parts":[{"type":"text","text":"Hello!"}]}},"id":1}'
```

### Adding New MCP Servers

1. Deploy the MCP server to your cluster
2. Add it to `MCP_SERVERS_JSON`:

```json
{
  "name": "my-new-mcp",
  "url": "http://my-new-mcp:8080/mcp",
  "headers": {"Authorization": "Bearer ${MY_TOKEN}"},
  "tools": ["tool1", "tool2"]
}
```

3. Add the token to secrets:

```yaml
stringData:
  my-token: "your-token-here"
```

4. Add the env var reference:

```yaml
- name: MY_TOKEN
  valueFrom:
    secretKeyRef:
      name: mcp-tokens
      key: my-token
```

## License

Apache 2.0

