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

## Notes

- KServe automatically creates Deployment, Services, and HPA
- Model serving requires GPU resources (1 GPU per replica)
- Initial model load can take 5-10 minutes
- The model is pulled from Hugging Face: `hf://Qwen/Qwen3-14B-AWQ`
