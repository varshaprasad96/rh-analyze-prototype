# OpenTelemetry Collector for MLflow Integration

This OTEL Collector receives traces from kagent agents (and other applications) via OTLP protocol and exports them to MLflow tracking server.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   kagent    │     │  OTEL Collector │     │     MLflow      │
│   Agent     │────▶│  :4317 (gRPC)   │────▶│  Tracking       │
│             │     │  :4318 (HTTP)   │     │  :5000          │
└─────────────┘     └─────────────────┘     └─────────────────┘
```

## Components

| File | Description |
|------|-------------|
| `configmap.yaml` | OTEL Collector configuration (receivers, processors, exporters) |
| `deployment.yaml` | Kubernetes Deployment for the collector |
| `service.yaml` | Kubernetes Service exposing OTLP endpoints |

## Configuration

The collector is configured to:
- **Receive** traces via OTLP (gRPC on port 4317, HTTP on port 4318)
- **Process** with batching and memory limiting
- **Export** to MLflow tracking server via OTLP/HTTP

## Deployment

```bash
# Replace namespace placeholder and deploy
NAMESPACE=mschimun

sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" configmap.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" deployment.yaml | oc apply -f -
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" service.yaml | oc apply -f -

# Verify deployment
oc get pods -n ${NAMESPACE} -l app=otel-collector
```

## Usage with kagent

Update your kagent Agent CRD to send traces to the collector:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
spec:
  declarative:
    deployment:
      env:
        - name: OTEL_TRACING_ENABLED
          value: "true"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector.NAMESPACE.svc.cluster.local:4317"
```

## Testing

Send a test trace:

```bash
# Port-forward the collector
oc port-forward -n ${NAMESPACE} svc/otel-collector 4317:4317

# Use otel-cli or any OTLP client to send traces
```

## Troubleshooting

Check collector logs:
```bash
oc logs -n ${NAMESPACE} -l app=otel-collector -f
```

The collector includes debug logging - check for trace reception and export status.

