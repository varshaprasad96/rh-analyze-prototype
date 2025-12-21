# MLflow Tracking Server

Complete MLflow deployment with PostgreSQL (metadata) and MinIO (artifacts) backends, plus OpenTelemetry integration for distributed tracing.

## Architecture

```
                                    ┌─────────────────┐
                                    │   MLflow UI     │
                                    │   :5000         │
                                    └────────┬────────┘
                                             │
┌─────────────────┐     ┌────────────────────┼────────────────────┐
│   Applications  │     │           MLflow Tracking Server        │
│   (kagent, etc) │────▶│   - Experiments                         │
└─────────────────┘     │   - Runs                                │
                        │   - Metrics                             │
                        │   - Traces (via OTEL)                   │
                        └────────────────────┼────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
           ┌────────┴────────┐      ┌────────┴────────┐
           │   PostgreSQL    │      │     MinIO       │
           │   (Metadata)    │      │   (Artifacts)   │
           │   :5432         │      │   :9000         │
           └─────────────────┘      └─────────────────┘
```

## Telemetry Architecture

MLflow receives distributed traces from all components via an OpenTelemetry Collector:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    MLflow UI                                              │
│                              (Traces Dashboard)                                           │
│                                   :5000                                                   │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              Complete Trace View                                    │  │
│  │  ┌─────────────┬───────────────────────────────────────────────────────────────┐  │  │
│  │  │ Span        │ Duration                                                      │  │  │
│  │  ├─────────────┼───────────────────────────────────────────────────────────────┤  │  │
│  │  │ kagent      │ ████████████████████████████████████████████████ 2.5s         │  │  │
│  │  │ └─ MCP call │   ████████████████████████████████████████ 2.1s               │  │  │
│  │  │   └─ search │     ██████████████████████████████████ 1.8s                   │  │  │
│  │  │     └─ HTTP │       ████████████████████████████ 1.5s                       │  │  │
│  │  │       └─ LS │         ████████████████████████ 1.3s                         │  │  │
│  │  │         └─vL│           ████████████████ 0.9s                               │  │  │
│  │  └─────────────┴───────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                             ▲
                                             │ OTLP/HTTP
                                             │
┌────────────────────────────────────────────┴───────────────────────────────────────────┐
│                               OTEL Collector                                            │
│                          (otel-collector:4317/4318)                                     │
│                                                                                         │
│   Receives: OTLP (gRPC :4317, HTTP :4318)                                              │
│   Exports:  OTLP/HTTP → MLflow :5000                                                   │
│   Pipelines: traces → batch → export                                                    │
└────────────────────────────────────────────▲───────────────────────────────────────────┘
                                             │
         ┌───────────────────────────────────┼───────────────────────────────────┐
         │                                   │                                   │
         │                                   │                                   │
┌────────┴────────┐   ┌──────────────────────┴──────────────────────┐   ┌───────┴────────┐
│     kagent      │   │           Vector Search MCP                 │   │  Llama Stack   │
│                 │   │                                             │   │                │
│ Service:        │   │ Service: vector-search-mcp                  │   │ Service:       │
│ hello-kagent    │   │                                             │   │ llama-stack    │
│                 │   │ Spans:                                      │   │                │
│ Spans:          │   │ - search_knowledge_base                     │   │ Spans:         │
│ - Agent logic   │   │   • query, vector_store_count               │   │ - Inference    │
│ - Tool calls    │   │   • max_results, search_mode                │   │ - RAG          │
│ - LLM requests  │   │ - search_vector_store (per store)           │   │ - Agents       │
│                 │   │   • vector_store_id, result_count           │   │ - Embeddings   │
│ Protocol:       │   │ - HTTP calls (auto-instrumented)            │   │                │
│ OTLP/gRPC :4317 │   │                                             │   │ Protocol:      │
└────────┬────────┘   │ Protocol: OTLP/gRPC :4317                   │   │ OTLP/HTTP :4318│
         │            └──────────────────────┬──────────────────────┘   └───────┬────────┘
         │                                   │                                   │
         └───────────────────────────────────┴───────────────────────────────────┘
                                             │
                                             │
                                    ┌────────┴────────┐
                                    │      vLLM       │
                                    │                 │
                                    │ Service:        │
                                    │ vllm-qwen3      │
                                    │                 │
                                    │ Spans:          │
                                    │ - Token gen     │
                                    │ - Batch process │
                                    │ - GPU inference │
                                    │                 │
                                    │ Protocol:       │
                                    │ OTLP/gRPC :4317 │
                                    └─────────────────┘
```

### Component OTEL Configuration

| Component | Service Name | OTEL Endpoint | Protocol |
|-----------|--------------|---------------|----------|
| **kagent** | `hello-kagent` | `otel-collector:4317` | gRPC |
| **Vector Search MCP** | `vector-search-mcp` | `otel-collector:4317` | gRPC |
| **Llama Stack** | `llama-stack` | `otel-collector:4318` | HTTP |
| **vLLM** | `vllm-qwen3` | `otel-collector:4317` | gRPC |

### Trace Flow Example

When a user asks "What is kagent?":

```
1. kagent                    → Receives user message, selects tool
   │
2. └─ MCP Tool Call          → Calls search_knowledge_base
      │
3.    └─ Vector Search MCP   → Searches vector store(s)
         │
4.       └─ HTTP Request     → POST /v1/vector_stores/.../search
            │
5.          └─ Llama Stack   → Processes RAG query
               │
6.             └─ vLLM       → Generates embeddings/response
```

Each step creates a span with:
- **Timing**: Start time, duration
- **Attributes**: Query text, result counts, model info
- **Errors**: Exception details if failed
- **Parent/Child**: Linked to show causality

### What You See in MLflow

The MLflow Traces tab shows:
- **Trace list**: All traces with duration, status
- **Trace detail**: Waterfall view of spans
- **Span attributes**: Custom metadata (query, scores, etc.)
- **Exceptions**: Stack traces for errors

## Components

| File | Description |
|------|-------------|
| `secrets.yaml` | Credentials for MinIO and PostgreSQL |
| `pvc.yaml` | Persistent Volume Claims for storage |
| `postgres.yaml` | PostgreSQL deployment for metadata |
| `minio.yaml` | MinIO deployment for S3-compatible artifact storage |
| `mlflow.yaml` | MLflow tracking server |

## Deployment

Deploy in order (dependencies first):

```bash
# Set your namespace
NAMESPACE=mschimun

# 1. Create secrets
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" secrets.yaml | oc apply -f -

# 2. Create persistent volumes
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" pvc.yaml | oc apply -f -

# 3. Deploy PostgreSQL
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" postgres.yaml | oc apply -f -

# 4. Wait for PostgreSQL to be ready
oc wait --for=condition=Ready pod -l app=mlflow-postgres -n ${NAMESPACE} --timeout=120s

# 5. Deploy MinIO
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" minio.yaml | oc apply -f -

# 6. Wait for MinIO to be ready
oc wait --for=condition=Ready pod -l app=mlflow-minio -n ${NAMESPACE} --timeout=120s

# 7. Deploy MLflow
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" mlflow.yaml | oc apply -f -

# 8. Verify deployment
oc get pods -n ${NAMESPACE} -l app=mlflow
oc get pods -n ${NAMESPACE} -l app=mlflow-postgres
oc get pods -n ${NAMESPACE} -l app=mlflow-minio
```

## Access

### MLflow UI

```bash
# Port-forward to access the UI
oc port-forward -n ${NAMESPACE} svc/mlflow 5000:5000

# Open in browser
open http://localhost:5000
```

### MinIO Console

```bash
# Port-forward to access MinIO console
oc port-forward -n ${NAMESPACE} svc/mlflow-minio 9001:9001

# Open in browser (credentials in secrets.yaml)
open http://localhost:9001
```

## Usage from Applications

### Python SDK

```python
import mlflow

# Set tracking URI
mlflow.set_tracking_uri("http://mlflow.NAMESPACE.svc.cluster.local:5000")

# Log an experiment
with mlflow.start_run():
    mlflow.log_param("model", "llama-3")
    mlflow.log_metric("accuracy", 0.95)
```

### Environment Variables

For containers in the same cluster:

```yaml
env:
  - name: MLFLOW_TRACKING_URI
    value: "http://mlflow.NAMESPACE.svc.cluster.local:5000"
  - name: MLFLOW_S3_ENDPOINT_URL
    value: "http://mlflow-minio.NAMESPACE.svc.cluster.local:9000"
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: mlflow-minio-secret
        key: MINIO_ROOT_USER
  - name: AWS_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: mlflow-minio-secret
        key: MINIO_ROOT_PASSWORD
```

## Service URLs

| Component | Internal URL |
|-----------|-------------|
| MLflow Tracking | `http://mlflow.NAMESPACE.svc.cluster.local:5000` |
| MLflow API | `http://mlflow.NAMESPACE.svc.cluster.local:5000/api/2.0/mlflow/` |
| MinIO API | `http://mlflow-minio.NAMESPACE.svc.cluster.local:9000` |
| MinIO Console | `http://mlflow-minio.NAMESPACE.svc.cluster.local:9001` |
| PostgreSQL | `mlflow-postgres.NAMESPACE.svc.cluster.local:5432` |

## Troubleshooting

### Check logs

```bash
# MLflow server logs
oc logs -n ${NAMESPACE} -l app=mlflow -f

# PostgreSQL logs
oc logs -n ${NAMESPACE} -l app=mlflow-postgres -f

# MinIO logs
oc logs -n ${NAMESPACE} -l app=mlflow-minio -f
```

### Common Issues

1. **MLflow fails to start**: Check PostgreSQL is ready first
2. **Artifact storage fails**: Ensure MinIO bucket exists (init container handles this)
3. **Connection refused**: Verify services are created and pods are running

## Cleanup

```bash
oc delete -f mlflow.yaml
oc delete -f minio.yaml
oc delete -f postgres.yaml
oc delete -f pvc.yaml
oc delete -f secrets.yaml
```

Note: Deleting PVCs will remove all stored data permanently.

