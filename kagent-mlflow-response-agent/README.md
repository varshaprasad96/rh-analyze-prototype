# kagent-mlflow-response-agent

MLflow ResponsesAgent deployed via kagent with A2A protocol support.

## Architecture

```
Kagenti UI / A2A Client
        │
        ▼
   kagent Agent (A2A)
        │
        ├── Tools → GitHub MCP
        │
        ▼
 MLflow ResponsesAgent Adapter
        │
        ├── RAG → Llama Stack Vector Store
        ├── LLM → Llama Stack (vLLM)
        └── Tracing → MLflow
```

## Features

- **MLflow ResponsesAgent**: Automatic tracing and logging
- **RAG**: Vector store retrieval via Llama Stack
- **A2A Protocol**: Handled by kagent
- **GitHub MCP Tools**: Repository exploration
- **Kagenti UI**: Discoverable agent

## Deployment

```bash
# Build image
oc start-build kagent-mlflow-response-agent --from-dir=. -n mschimun --follow

# Deploy all resources
oc apply -f k8s/

# Restart deployments
oc rollout restart deployment/kagent-mlflow-response-adapter -n mschimun
oc rollout restart deployment/kagent-mlflow-response-agent -n mschimun
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLAMASTACK_URL` | Llama Stack API URL | `http://llama-stack-service:8321` |
| `LLAMASTACK_MODEL` | Model name | `vllm-inference-1/qwen3-14b-awq` |
| `VECTOR_STORE_ID` | Vector store for RAG | (from ConfigMap) |
| `MLFLOW_TRACKING_URI` | MLflow server | `http://mlflow:5000` |
| `MLFLOW_EXPERIMENT` | Experiment name | `kagent-mlflow-response-agent` |

## Testing

```bash
# Port forward to agent
oc port-forward -n mschimun svc/kagent-mlflow-response-agent 8080:8080 &

# Test A2A discovery
curl http://localhost:8080/.well-known/agent.json

# Test chat
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello!"}]
      }
    }
  }'
```

