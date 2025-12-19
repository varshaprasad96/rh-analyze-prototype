# Vector Store Setup

Automatically populates Llama Stack vector store with documentation from https://github.com/varshaprasad96/rh-analyze-prototype/tree/main/docs

## Overview

This component:
- Fetches markdown documentation from Varsha's repository
- Uploads files to Llama Stack Files API
- Creates a vector store with granite-embedding-125m
- Populates the vector store with documentation
- Runs automatically as part of `make deploy`

## Files

- **`setup-vectorstore.py`** - Python script that performs the setup
- **`requirements.txt`** - Python dependencies
- **`Dockerfile`** - Container image definition
- **`buildconfig.yaml`** - OpenShift BuildConfig
- **`job.yaml`** - Kubernetes Job manifest

## Documentation Files

The following files are fetched and added to the vector store:
- architecture-proposal.md (40KB)
- cagent.md (4.7KB)
- kagent.md (5.2KB)
- kagenti.md (6.8KB)
- llama-stack.md (7.5KB)
- mlflow.md (6.9KB)

## Automated Deployment

The vector store is automatically set up during `make deploy`:

```bash
make deploy NAMESPACE=my-namespace
```

Deployment flow:
1. vLLM deployment
2. Agent image build (parallel)
3. Llama Stack deployment
4. **Vector store setup** ← Automatic
5. Agent deployment

## Manual Deployment

To set up the vector store independently:

```bash
# Build the image
make build-vectorstore NAMESPACE=my-namespace

# Run the setup Job
make deploy-vectorstore NAMESPACE=my-namespace
```

## Verification

Check that the vector store was created:

```bash
# Check Job status
oc get job vectorstore-setup -n my-namespace

# Check Job logs
oc logs job/vectorstore-setup -n my-namespace

# Query Llama Stack for vector stores
oc exec -n my-namespace deployment/llama-stack -- \
  curl -s http://localhost:8321/v1/vector_stores
```

## Vector Store Details

- **Name:** `docs-vectorstore`
- **Embedding Model:** granite-embedding-125m
- **Chunking Strategy:** Fixed (1000 tokens, 100 overlap)
- **Files:** 6 markdown documentation files

## Using the Vector Store

Once populated, agents can query the vector store for RAG:

```yaml
# In agent configuration
rag:
  knowledge_base:
    vector_store_id: "docs-vectorstore"
    top_k: 5
```

## Troubleshooting

### Job Failed
```bash
# Check logs
oc logs job/vectorstore-setup -n my-namespace

# Common issues:
# - Llama Stack not ready
# - Network connectivity to GitHub
# - API endpoint mismatch
```

### Re-run Setup
```bash
# Delete the Job
oc delete job vectorstore-setup -n my-namespace

# Run again
make deploy-vectorstore NAMESPACE=my-namespace
```

### Check Vector Store
```bash
# List all vector stores
oc exec -n my-namespace deployment/llama-stack -- \
  curl -s http://localhost:8321/v1/vector_stores | jq

# Check specific vector store
oc exec -n my-namespace deployment/llama-stack -- \
  curl -s http://localhost:8321/v1/vector_stores/<store-id> | jq
```

