# Llama Stack Deployment

This directory contains the configuration for deploying Llama Stack using the LlamaStackDistribution (LSD) operator.

## Files

- **`llamastackdistribution.yaml`** - LlamaStackDistribution CR template (uses NAMESPACE_PLACEHOLDER)
- **`configmap-template.yaml`** - Llama Stack configuration template (uses NAMESPACE_PLACEHOLDER)
- **`configmap.yaml`** - Exported original configuration (reference only)

## Llama Stack Information

**Deployment:** llama-stack  
**Service:** llama-stack-service  
**Port:** 8321  
**Endpoint:** `http://llama-stack-service.<namespace>.svc.cluster.local:8321`

## Deployment

The Llama Stack is deployed automatically using the Makefile:

```bash
# Deploy to a specific namespace (after vLLM is deployed)
make deploy-llamastack NAMESPACE=my-namespace

# Or deploy both vLLM and Llama Stack together
make deploy NAMESPACE=my-namespace
```

## Manual Deployment

If you need to deploy manually:

```bash
# Replace namespace placeholder and deploy ConfigMap
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' configmap-template.yaml | oc apply -f -

# Deploy LlamaStackDistribution
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' llamastackdistribution.yaml | oc apply -f -

# Wait for Llama Stack to be ready
oc wait --for=condition=Ready llamastackdistribution/llama-stack -n my-namespace --timeout=300s
```

## Configuration

The ConfigMap contains the Llama Stack run.yaml which:
- Connects to the vLLM model in the same namespace
- Configures vector storage (Milvus)
- Enables agents, RAG, files, inference, and tool APIs
- Sets up embedding model (granite-embedding-125m)

## Notes

- Requires vLLM model to be deployed and ready first
- The LSD operator automatically creates Deployment, Service, and ServiceAccount
- ConfigMap URL automatically references the vLLM model in the same namespace
- Llama Stack is ready when the pod is Running and health check passes
