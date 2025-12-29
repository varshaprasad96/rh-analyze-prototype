## kagent-mlflow-agent (A2A via kagent, server-side MLflow, Llama Stack vector store RAG)

This package adds a **minimal OpenAI-compatible adapter** that:

- Receives `POST /v1/chat/completions` requests from **kagent** (`ModelConfig.provider: OpenAI`)
- Performs **retrieval** from a **Llama Stack vector store** (`/v1/vector_stores/{id}/search`)
- Calls **Llama Stack chat completions** (backed by **vLLM**) (`/v1/chat/completions`)
- Logs each request/response **server-side to MLflow** (so Kagenti UI chats are tracked)

Why this exists (vs Varsha’s pure Declarative agent): Varsha’s approach keeps MLflow **off** the serving path. Your requirement is that **Kagenti UI chats must appear in MLflow** (server-side), which requires logging inside the serving path.

### Components

- **Adapter service** (`app.py`): OpenAI Chat Completions compatible endpoint + MLflow logging + vector store retrieval.
- **kagent ModelConfig** (`k8s/modelconfig.yaml`): points to the adapter `/v1`.
- **kagent Agent** (`k8s/agent.yaml`): A2A-enabled agent discoverable by Kagenti UI.

### Configuration (adapter)

The adapter is configured via environment variables:

- **`LLAMASTACK_URL`**: Llama Stack base URL (no `/v1`), e.g. `http://llama-stack-service:8321`
- **`LLAMASTACK_MODEL`**: model name, default `vllm-inference-1/qwen3-14b-awq`
- **`VECTOR_STORE_ID`**: vector store id used for retrieval (typically from `vectorstore-config` ConfigMap)
- **`SEARCH_MODE`**: `vector|keyword|hybrid` (default `hybrid`)
- **`MAX_RESULTS`**: retrieval top-k (default `5`)
- **`MLFLOW_TRACKING_URI`**: MLflow server URL, e.g. `http://mlflow:5000`
- **`MLFLOW_EXPERIMENT`**: MLflow experiment name (default `kagent-mlflow-agent`)

### Deploy (OpenShift)

All YAMLs are templates with `NAMESPACE_PLACEHOLDER`.

1) Build the adapter image:

```bash
oc apply -f k8s/buildconfig.yaml -n mschimun
oc start-build kagent-mlflow-agent -n mschimun --from-dir=. --follow
```

2) Deploy the adapter + kagent resources:

```bash
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/secret.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/deployment.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/service.yaml | oc apply -f -

sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/modelconfig.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/agent.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" k8s/agent-service-8000.yaml | oc apply -f -
```

### Verify

- **Adapter health**:

```bash
oc get pods -n mschimun -l app=kagent-mlflow-agent
oc logs -n mschimun -l app=kagent-mlflow-agent --tail=50
```

- **A2A agent card** (served by kagent runtime, not the adapter):

```bash
oc port-forward -n mschimun svc/kagent-mlflow-agent 8080:8080
curl http://localhost:8080/.well-known/agent.json | jq .
```

- **MLflow**: open the MLflow UI and confirm new runs appear under the experiment.


