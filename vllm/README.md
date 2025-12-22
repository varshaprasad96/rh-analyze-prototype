# vLLM Model Deployment

This directory contains the configuration for deploying a vLLM model using KServe model serving.

## Files

- **`servingruntime.yaml`** - vLLM ServingRuntime configuration (uses NAMESPACE_PLACEHOLDER)
- **`secret.yaml`** - Model connection secret with Hugging Face URI (uses NAMESPACE_PLACEHOLDER)
- **`inferenceservice.yaml`** - KServe InferenceService template (uses NAMESPACE_PLACEHOLDER)

## Model Information

**Model:** Qwen3-14B-AWQ  
**Framework:** vLLM (via KServe)  
**Endpoint:** `http://qwen3-14b-awq-predictor.<namespace>.svc.cluster.local:8080`  

## Deployment

The model is deployed automatically using the Makefile:

```bash
# Deploy to a specific namespace
make deploy-vllm NAMESPACE=my-namespace

# Or deploy both vLLM and Llama Stack together
make deploy NAMESPACE=my-namespace
```

## Manual Deployment

If you need to deploy manually:

```bash
# Replace namespace placeholder
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' inferenceservice.yaml | oc apply -f -

# Wait for model to be ready
oc wait --for=condition=Ready inferenceservice/qwen3-14b-awq -n my-namespace --timeout=600s
```

## Telemetry (OpenTelemetry)

vLLM has native OpenTelemetry support for distributed tracing. The ServingRuntime is configured to send traces to an OTEL Collector:

| Configuration | Value | Description |
|--------------|-------|-------------|
| `--otlp-traces-endpoint` | `http://otel-collector.<namespace>.svc.cluster.local:4317` | OTEL Collector gRPC endpoint |
| `OTEL_SERVICE_NAME` | `vllm-qwen3` | Service name in traces |
| `OTEL_EXPORTER_OTLP_TRACES_INSECURE` | `true` | Allow non-TLS connection |

### What's Traced

vLLM traces include:
- Token generation latency
- Batch processing time
- Model inference duration
- Request queue time

### End-to-End Tracing

With OTEL enabled on vLLM, Llama Stack, and kagent, you get complete visibility:

```
User Request → kagent → Llama Stack → vLLM (GPU inference) → Response
     └── traces ──────────────────────────────────────────────────┘
                              │
                     OTEL Collector → MLflow
```

## Notes

- KServe automatically creates Deployment, Services, and HPA
- Model serving requires GPU resources (1 GPU per replica)
- Initial model load can take 5-10 minutes
- The model is pulled from Hugging Face: `hf://Qwen/Qwen3-14B-AWQ`
- **Important:** The OTEL endpoint in `servingruntime.yaml` uses `NAMESPACE_PLACEHOLDER` - ensure the OTEL Collector is deployed in the same namespace or update the endpoint accordingly
