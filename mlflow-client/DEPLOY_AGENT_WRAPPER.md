# Deploying MLflow Agent Wrapper to Cluster

This guide shows how to deploy and test the Llamastack Agent Wrapper in your Kubernetes/OpenShift cluster.

## Prerequisites

- MLflow tracking server running in cluster (you already have this) - **Keep this running!**
- MLflow MinIO running in cluster (you already have this) - **Keep this running!**
- Llamastack server running in cluster
- Access to the cluster namespace where MLflow is deployed

## Important: Two Different MLflow Services

**MLflow Tracking Server** (already running):
- Purpose: Tracks experiments, stores model metadata, provides UI
- Service: `mlflow` on port 5000
- **Keep this running** - it's needed for the model server to load models

**MLflow Model Server** (what we're deploying):
- Purpose: Serves a specific logged model for inference
- Service: `mlflow-agent-server` on port 8080
- Connects to the tracking server to load the model
- This is a separate service that runs alongside the tracking server

## Step 1: Log the Agent Wrapper to MLflow

First, you need to log the agent wrapper to your existing MLflow server. You can do this either:

### Option A: From Local Machine (with cluster access)

```bash
# Set environment variables pointing to your cluster MLflow
export MLFLOW_TRACKING_URI="http://mlflow.<namespace>.svc.cluster.local:5000"
# Or if you have port-forwarding:
# export MLFLOW_TRACKING_URI="http://localhost:5000"

# Set Llamastack connection details
export LLAMASTACK_BASE_URL="http://llamastack-with-userconfig-service.<namespace>.svc.cluster.local:8321"
export LLAMASTACK_AGENT_ID="default-agent"  # Update with your agent ID
export LLAMASTACK_API_KEY="fake"

# Set MinIO credentials (if needed for artifact storage)
export MLFLOW_S3_ENDPOINT_URL="http://mlflow-minio.<namespace>.svc.cluster.local:9000"
export AWS_ACCESS_KEY_ID="minio"  # Default MinIO credentials
export AWS_SECRET_ACCESS_KEY="miniopass123"  # Default MinIO credentials

# Log the agent wrapper
cd mlflow-client
python log_llamastack_agent_direct.py
```

### Option B: From a Pod in the Cluster

If you prefer to run from within the cluster:

```bash
# Create a job pod to log the model
oc run mlflow-logger --image=python:3.12 --restart=Never --rm -it -- \
  sh -c "
    pip install mlflow openai pydantic boto3 requests && \
    git clone <your-repo> /tmp/repo && \
    cd /tmp/repo/mlflow-client && \
    export MLFLOW_TRACKING_URI='http://mlflow.<namespace>.svc.cluster.local:5000' && \
    export LLAMASTACK_BASE_URL='http://llamastack-with-userconfig-service.<namespace>.svc.cluster.local:8321' && \
    export LLAMASTACK_AGENT_ID='default-agent' && \
    python log_llamastack_agent_direct.py
  "
```

## Step 2: Deploy the Agent Server

Once the model is logged to MLflow, deploy the agent server:

```bash
# Replace NAMESPACE_PLACEHOLDER with your actual namespace
export NAMESPACE="your-namespace"  # e.g., "rh-analyze" or "mlflow"

# Deploy the agent server
sed "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" \
  deployment-yamls/mlflow-agent-server.yaml | \
  oc apply -f -

# Wait for deployment to be ready
oc wait --for=condition=available \
  deployment/mlflow-agent-server \
  -n ${NAMESPACE} \
  --timeout=300s
```

## Step 3: Verify Deployment

Check that the agent server is running:

```bash
# Check pods
oc get pods -n ${NAMESPACE} | grep mlflow-agent-server

# Check service
oc get svc -n ${NAMESPACE} | grep mlflow-agent-server

# Check logs
oc logs -f deployment/mlflow-agent-server -n ${NAMESPACE}
```

## Step 4: Test the Agent

### Option A: From within the cluster

```bash
# Port-forward the service (if needed)
oc port-forward svc/mlflow-agent-server 8080:8080 -n ${NAMESPACE}

# Test with curl
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": "What is OpenShift?"
      }
    ]
  }'
```

### Option B: From a pod in the cluster

```bash
# Test from another pod
oc run test-agent --image=curlimages/curl --restart=Never --rm -it -- \
  curl -X POST http://mlflow-agent-server.${NAMESPACE}.svc.cluster.local:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{
      "input": [
        {
          "role": "user",
          "content": "What is OpenShift?"
        }
      ]
    }'
```

### Option C: Using Python

```python
import requests

response = requests.post(
    "http://mlflow-agent-server.<namespace>.svc.cluster.local:8080/invocations",
    json={
        "input": [
            {
                "role": "user",
                "content": "What is OpenShift?"
            }
        ]
    },
    headers={"Content-Type": "application/json"},
    timeout=120,
)

print(response.json())
```

## Troubleshooting

### Agent Server Not Starting

1. Check logs:
   ```bash
   oc logs deployment/mlflow-agent-server -n ${NAMESPACE}
   ```

2. Verify MLflow model exists:
   ```bash
   # Port-forward MLflow UI or check via API
   curl http://mlflow.${NAMESPACE}.svc.cluster.local:5000/api/2.0/mlflow/models/search
   ```

3. Verify environment variables:
   ```bash
   oc describe deployment/mlflow-agent-server -n ${NAMESPACE}
   ```

### Connection Issues

1. Verify Llamastack is accessible:
   ```bash
   oc run test-llamastack --image=curlimages/curl --restart=Never --rm -it -- \
     curl http://llamastack-with-userconfig-service.${NAMESPACE}.svc.cluster.local:8321/v1/health
   ```

2. Check network policies if connections fail

### Model Not Found

If you get "model not found" errors:

1. Verify the model was logged:
   ```bash
   # Check MLflow UI or API
   curl http://mlflow.${NAMESPACE}.svc.cluster.local:5000/api/2.0/mlflow/models/search?name=llamastack-agent-wrapper
   ```

2. Update the model path in the deployment if needed:
   ```yaml
   # In mlflow-agent-server.yaml, update the model path:
   -m models:/llamastack-agent-wrapper/latest
   # Or use a specific version:
   -m models:/llamastack-agent-wrapper/1
   ```

## Updating the Agent

To update the agent after making changes:

1. Log the new version to MLflow (Step 1)
2. Restart the deployment:
   ```bash
   oc rollout restart deployment/mlflow-agent-server -n ${NAMESPACE}
   ```

## Cleanup

To remove the agent server:

```bash
oc delete deployment mlflow-agent-server -n ${NAMESPACE}
oc delete svc mlflow-agent-server -n ${NAMESPACE}
```

Note: This does NOT delete the MLflow tracking server or the logged model.

