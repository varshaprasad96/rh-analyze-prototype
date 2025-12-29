# kagent-mlflow-response-agent

MLflow ResponsesAgent deployed via kagent with A2A protocol support, native RAG via Llama Stack, and dynamic MCP tools.

## Architecture

```
Kagenti UI / A2A Client
        │
        ▼
   kagent Agent (A2A + SSE streaming)
        │
        ▼
 MLflow ResponsesAgent Adapter (/v1/chat/completions)
        │
        ▼
   Llama Stack (/v1/responses)
        │
        ├── file_search → Vector Store (RAG)
        ├── mcp → GitHub MCP, other tools
        └── LLM → vLLM inference
```

## Features

- **MLflow ResponsesAgent**: Automatic tracing and logging of all interactions
- **Native RAG**: Llama Stack `file_search` tool with configurable vector stores
- **Native MCP Tools**: Dynamic MCP server configuration with authentication
- **A2A Protocol**: Handled by kagent with SSE streaming
- **Conversation Continuity**: `previous_response_id` for multi-turn conversations
- **Kagenti UI**: Discoverable agent via proxy

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLAMASTACK_URL` | Llama Stack API URL | `http://llama-stack-service:8321` |
| `LLAMASTACK_MODEL` | Model name | `vllm-inference-1/qwen3-14b-awq` |
| `VECTOR_STORE_IDS` | Comma-separated or JSON array of vector store IDs | (from ConfigMap) |
| `MAX_RESULTS` | Max results per vector store search | `10` |
| `MCP_TOOLS` | JSON array of MCP server configs (see below) | `[]` |
| `MLFLOW_TRACKING_URI` | MLflow server URL | `http://mlflow:5000` |
| `MLFLOW_EXPERIMENT` | MLflow experiment name | `kagent-mlflow-response-agent` |

### MCP Tools Configuration

MCP tools are configured via the `MCP_TOOLS` environment variable as a JSON array.

**Important**: Use `headers` with full `Authorization: Bearer <token>` (required for Llama Stack ≤0.3.x):

```json
[
  {
    "server_url": "https://api.githubcopilot.com/mcp/x/repos/readonly",
    "server_label": "GitHub",
    "headers": {"Authorization": "Bearer YOUR_GITHUB_TOKEN"}
  },
  {
    "server_url": "http://internal-mcp:8080/mcp",
    "server_label": "Internal Tools"
  }
]
```

Create the secret:
```bash
oc create secret generic mcp-tools-config \
  --from-literal=MCP_TOOLS='[{"server_url":"https://api.githubcopilot.com/mcp/x/repos/readonly","server_label":"GitHub","headers":{"Authorization":"Bearer YOUR_TOKEN"}}]' \
  -n mschimun
```

### Vector Store Configuration

Vector stores can be configured as:
- Single ID: `vs_abc123`
- Comma-separated: `vs_abc123,vs_def456`
- JSON array: `["vs_abc123", "vs_def456"]`

## Deployment

### Prerequisites

- OpenShift cluster with kagent operator installed
- Llama Stack with vLLM backend
- MLflow tracking server
- Vector store created in Llama Stack

### Deploy

```bash
# 1. Create the MCP tools secret (update with your token)
oc apply -f k8s/mcp-tools-secret.yaml

# 2. Build the adapter image
oc apply -f k8s/buildconfig.yaml
oc start-build kagent-mlflow-response-agent --from-dir=. -n mschimun --follow

# 3. Deploy all resources
oc apply -f k8s/secret.yaml
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/modelconfig.yaml
oc apply -f k8s/agent.yaml

# 4. (Optional) Build and deploy Kagenti proxy for UI visibility
cd proxy/
oc apply -f buildconfig.yaml
oc start-build kagent-response-proxy --from-dir=. -n mschimun --follow
```

### Restart after changes

```bash
oc rollout restart deployment/kagent-mlflow-response-adapter -n mschimun
```

## Testing

### Health Check

```bash
oc port-forward -n mschimun svc/kagent-mlflow-response-adapter 8080:8080 &
curl http://localhost:8080/healthz
```

Expected response:
```json
{
  "ok": true,
  "agent_ready": true,
  "mlflow_enabled": true,
  "vector_stores": ["vs_xxx"],
  "mcp_tools_count": 1
}
```

### Test Chat (via adapter)

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "messages": [{"role": "user", "content": "List 3 kubernetes repos on GitHub"}]
  }'
```

### Test A2A (via kagent)

```bash
oc port-forward -n mschimun svc/kagent-mlflow-response-agent 8081:8080 &

# Discovery
curl http://localhost:8081/.well-known/agent.json

# Send message
curl -X POST http://localhost:8081/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "What documents do you have?"}]
      }
    }
  }'
```

## Components

| Component | Description |
|-----------|-------------|
| `agent.py` | MLflow ResponsesAgent with Llama Stack `/v1/responses` integration |
| `server.py` | FastAPI adapter providing OpenAI-compatible `/v1/chat/completions` |
| `k8s/deployment.yaml` | Adapter deployment |
| `k8s/agent.yaml` | kagent Agent CRD |
| `k8s/modelconfig.yaml` | kagent ModelConfig pointing to adapter |
| `k8s/mcp-tools-secret.yaml` | MCP tools configuration |
| `proxy/` | Nginx proxy for Kagenti UI compatibility |

## Troubleshooting

### MCP 401 Unauthorized

Ensure you're using `headers` format (not `authorization`):
```json
{"headers": {"Authorization": "Bearer TOKEN"}}
```

### No vector store results

Check the vector store ID exists:
```bash
curl http://llama-stack:8321/v1/vector_stores
```

### MLflow not tracking

Verify `MLFLOW_TRACKING_URI` is set and accessible from the pod.
