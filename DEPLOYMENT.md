# Deployment Guide

Quick reference for deploying the multi-agent AI platform components.

## Prerequisites

1. OpenShift cluster access (configured in `.env.local`)
2. Logged in to the cluster: `make login`
3. OpenShift AI operators installed:
   - KServe operator (for vLLM model serving)
   - Llama Stack operator (LSD)

## Quick Deploy

Deploy both vLLM and Llama Stack to a namespace:

```bash
# Deploy to default namespace (mschimun)
make deploy

# Deploy to custom namespace
make deploy NAMESPACE=my-team

# Deploy to analytics namespace
make deploy NAMESPACE=analytics
```

## Step-by-Step Deploy

Deploy components individually:

```bash
# 1. Deploy vLLM model first
make deploy-vllm NAMESPACE=my-namespace

# 2. Wait for vLLM to be ready (automatic)

# 3. Deploy Llama Stack
make deploy-llamastack NAMESPACE=my-namespace
```

## Check Status

```bash
# Check deployment status
make status NAMESPACE=my-namespace

# Check specific components
oc get inferenceservice -n my-namespace
oc get llamastackdistribution -n my-namespace
oc get pods -n my-namespace
```

## Clean Up

```bash
# Remove deployments (keeps namespace)
make clean NAMESPACE=my-namespace

# Remove namespace entirely
oc delete namespace my-namespace
```

## Deployment Timeline

- **Namespace creation:** < 10 seconds
- **vLLM model deployment:** 5-10 minutes (model download + GPU init)
- **Llama Stack deployment:** 1-2 minutes
- **Total:** ~6-12 minutes for complete deployment

## Endpoints

After successful deployment:

```bash
# vLLM inference endpoint
http://qwen3-14b-awq-predictor.<namespace>.svc.cluster.local:8080/v1

# Llama Stack API endpoint
http://lsd-genai-playground-service.<namespace>.svc.cluster.local:8321/v1

# Test vLLM
curl http://qwen3-14b-awq-predictor.<namespace>.svc.cluster.local:8080/v1/models

# Test Llama Stack
curl http://lsd-genai-playground-service.<namespace>.svc.cluster.local:8321/v1/health
```

## Resource Requirements

### vLLM Model
- **GPU:** 1x NVIDIA GPU
- **CPU:** 2-4 cores
- **Memory:** 4-8Gi
- **Storage:** Model downloaded to ephemeral storage

### Llama Stack
- **CPU:** 250m-2 cores
- **Memory:** 500Mi-12Gi
- **Storage:** SQLite databases in ephemeral storage

## Troubleshooting

### vLLM not starting
```bash
# Check pod logs
oc logs -n <namespace> -l serving.kserve.io/inferenceservice=qwen3-14b-awq

# Check events
oc get events -n <namespace> --sort-by='.lastTimestamp'

# Common issues:
# - No GPU nodes available
# - Model download timeout
# - Insufficient memory
```

### Llama Stack not connecting to vLLM
```bash
# Check Llama Stack logs
oc logs -n <namespace> -l app.kubernetes.io/part-of=llama-stack

# Verify vLLM is accessible
oc exec -n <namespace> deployment/lsd-genai-playground -- \
  curl http://qwen3-14b-awq-predictor.<namespace>.svc.cluster.local:8080/v1/models
```

## Multi-Namespace Deployment

Deploy to multiple namespaces for team isolation:

```bash
# Deploy for team A
make deploy NAMESPACE=team-a

# Deploy for team B  
make deploy NAMESPACE=team-b

# Deploy for team C
make deploy NAMESPACE=team-c

# Each team gets their own isolated stack
```

