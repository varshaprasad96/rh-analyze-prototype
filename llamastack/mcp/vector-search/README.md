# Llama Stack Vector Search MCP Server

A generic, reusable MCP server that exposes Llama Stack's vector store search API to AI agents via the Model Context Protocol (MCP).

## Why This Exists

**Problem:** kagent doesn't have native Llama Stack RAG support, and we wanted to reuse our existing Llama Stack vector stores (hybrid search, metadata, etc.) without losing the investment.

**Solution:** A config-driven FastMCP server that wraps Llama Stack's `/v1/vector_stores/{id}/search` API and exposes a simple `search_knowledge_base` tool to any MCP-compatible agent framework.

## Benefits

✅ **Generic & Reusable** - Same image, multiple deployments with different configs  
✅ **Simple LLM Interface** - Agent only provides search query, not vector store IDs or URLs  
✅ **Multi-Framework** - Works with kagent, or any framework that supports MCP tools  
✅ **Production-Ready** - ConfigMap-based config, health probes, resource limits  
✅ **Multi-Store Support** - Can search across multiple vector stores and combine results

## Architecture

```
┌─────────────┐    MCP/HTTP     ┌──────────────────┐   Llama Stack API   ┌─────────────────┐
│   kagent    │ ──────────────> │  FastMCP Server  │ ──────────────────> │  Llama Stack    │
│   Agent     │  streamable-http │  (vector-search) │   /v1/vector_stores │  Vector Store   │
└─────────────┘                  └──────────────────┘                      └─────────────────┘
                                          │
                                          │ Config from
                                          ▼
                                  ┌──────────────┐
                                  │  ConfigMap   │
                                  │  (env vars)  │
                                  └──────────────┘
```

## Tool Interface

**What the LLM sees:**
```python
search_knowledge_base(query: str) -> str
```

**What's configured via ConfigMap:**
- `llamastack_url` - Llama Stack service URL
- `vector_store_ids` - Comma-separated list of vector store IDs to search
- `max_results` - Maximum results to return (default: 3)
- `search_mode` - `vector`, `keyword`, or `hybrid` (default: vector)
- `rewrite_query` - Whether to rewrite queries for better results (default: true)
- `combine_results` - Combine and sort results from multiple stores (default: true)

## Files

- **`server.py`** - FastMCP server with `search_knowledge_base` tool
- **`requirements.txt`** - Python dependencies (fastmcp, httpx)
- **`Dockerfile`** - Container image (Red Hat UBI9 Python 3.11)
- **`buildconfig.yaml`** - OpenShift BuildConfig
- **`configmap.yaml`** - Configuration template with env vars
- **`deployment.yaml`** - Kubernetes Deployment with probes & resource limits
- **`service.yaml`** - Kubernetes Service exposing port 8080

## Deployment

### Prerequisites

1. Llama Stack deployed with vector store
2. Vector store populated with documents

### Automated (Recommended)

```bash
# Build and deploy everything
make deploy-vectorsearch-mcp NAMESPACE=mschimun

# The Makefile will:
# 1. Verify vector store exists
# 2. Build FastMCP image
# 3. Create ConfigMap with vector store ID
# 4. Deploy FastMCP server
# 5. Wait for readiness
```

### Manual Deployment

```bash
# 1. Build image
cd llamastack/mcp/vector-search
oc apply -f buildconfig.yaml -n mschimun
oc start-build vector-search-mcp -n mschimun --from-dir=. --follow

# 2. Get vector store ID from existing config
VECTOR_STORE_ID=$(oc get configmap vectorstore-config -n mschimun -o jsonpath='{.data.VECTOR_STORE_ID}')

# 3. Create ConfigMap
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" configmap.yaml | \
  sed "s/VECTOR_STORE_ID_PLACEHOLDER/$VECTOR_STORE_ID/g" | \
  oc apply -f -

# 4. Deploy server
IMAGE=$(oc get imagestream vector-search-mcp -n mschimun -o jsonpath='{.status.tags[0].items[0].dockerImageReference}')
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" deployment.yaml | \
  sed "s|IMAGE_PLACEHOLDER|$IMAGE|g" | \
  oc apply -f -

# 5. Create service
sed "s/NAMESPACE_PLACEHOLDER/mschimun/g" service.yaml | oc apply -f -

# 6. Verify deployment
oc get pods -n mschimun -l app=vector-search-mcp
oc logs -n mschimun -l app=vector-search-mcp
```

## Usage with kagent

### 1. Create RemoteMCPServer CRD

```yaml
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: llamastack-rag
  namespace: mschimun
spec:
  url: "http://vector-search-mcp.mschimun.svc.cluster.local:8080/mcp"
  timeout: 30s
  sseReadTimeout: 5m0s
  description: "Llama Stack vector store search for RAG"
  tools: ["search_knowledge_base"]
```

Apply:
```bash
oc apply -f kagent-helloworld/vector-search-mcpserver.yaml
```

### 2. Add to Agent Configuration

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: hello-kagent
  namespace: mschimun
spec:
  type: Declarative
  declarative:
    modelConfig: llama-stack-model
    systemMessage: |
      You are a helpful AI assistant with access to a knowledge base.
      
      IMPORTANT: When answering questions about multi-agent platforms,
      ML platforms, or cloud-native deployment, ALWAYS use the
      search_knowledge_base tool first.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: llamastack-rag
          toolNames:
            - search_knowledge_base
```

### 3. Verify in kagent UI

1. Navigate to: `https://kagent-ui-kagent.apps.rosa.<cluster>.openshiftapps.com`
2. Select your agent and namespace
3. Ask: "What is kagent?"
4. The agent should use `search_knowledge_base` and return RAG-enhanced answers

## Multi-Instance Deployment

Deploy multiple MCP servers for different vector stores using the **same image**:

### Example: Team-Specific Knowledge Bases

```bash
# Team A - ML Platform docs
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: vector-search-config-ml
  namespace: mschimun
data:
  llamastack_url: "http://llama-stack-service.mschimun.svc.cluster.local:8321"
  vector_store_ids: "vs_ml-platform-docs"
  max_results: "5"
  search_mode: "hybrid"
EOF

# Deploy with different name
sed 's/vector-search-mcp/vector-search-ml/g' deployment.yaml | \
  sed 's/vector-search-config/vector-search-config-ml/g' | \
  oc apply -f -
```

### Example: Multi-Store Search

Search across multiple vector stores in a single query:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vector-search-config-combined
data:
  llamastack_url: "http://llama-stack-service.mschimun.svc.cluster.local:8321"
  vector_store_ids: "vs_ml-docs,vs_platform-docs,vs_api-docs"
  max_results: "5"
  search_mode: "vector"
  combine_results: "true"  # Sort all results by score
```

## Configuration Reference

### ConfigMap Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `llamastack_url` | Llama Stack base URL | - | `http://llama-stack-service.mschimun.svc:8321` |
| `vector_store_ids` | Comma-separated vector store IDs | - | `vs_abc123,vs_def456` |
| `max_results` | Max results per query | `3` | `5` |
| `search_mode` | Search mode | `vector` | `vector`, `keyword`, `hybrid` |
| `rewrite_query` | Rewrite queries for better results | `true` | `true`, `false` |
| `combine_results` | Combine multi-store results by score | `true` | `true`, `false` |
| `llamastack_token` | Optional bearer token | `""` | `sk-...` |

### Deployment Configuration

The deployment includes:
- **Resource limits**: 500m CPU, 512Mi memory
- **Health probes**: TCP-based liveness & readiness
- **Image pull policy**: Always (pulls latest on restart)
- **Transport**: `streamable-http` (kagent-compatible MCP transport)

## Testing

### Test MCP Server Health

```bash
# Check pod status
oc get pods -n mschimun -l app=vector-search-mcp

# Check logs
oc logs -n mschimun -l app=vector-search-mcp --tail=50

# Should see:
# FastMCP Vector Search Server
#   Llama Stack: http://llama-stack-service...
#   Vector Stores: ['vs_...']
#   Max Results: 3
#   Starting MCP server... on http://0.0.0.0:8080/mcp
```

### Test Tool Discovery

```bash
# Port forward
oc port-forward -n mschimun svc/vector-search-mcp 8085:8080 &

# List tools (via MCP)
curl -X POST http://localhost:8085/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }' | jq .

# Should return:
# {
#   "jsonrpc": "2.0",
#   "result": {
#     "tools": [
#       {
#         "name": "search_knowledge_base",
#         "description": "Search the documentation knowledge base...",
#         ...
#       }
#     ]
#   }
# }
```

### Test Search

```bash
# Call search tool
curl -X POST http://localhost:8085/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_knowledge_base",
      "arguments": {"query": "What is kagent?"}
    },
    "id": 2
  }' | jq .
```

### Test via kagent UI

1. Open kagent UI
2. Select agent with `llamastack-rag` MCP
3. Ask: "What is MLflow?" or "Explain cagent vs kagent"
4. Agent should call `search_knowledge_base` and return context-rich answers

## Troubleshooting

### Pod not starting

```bash
# Check events
oc describe pod -n mschimun -l app=vector-search-mcp

# Check ConfigMap
oc get configmap vector-search-config -n mschimun -o yaml

# Common issues:
# - Missing VECTOR_STORE_ID in ConfigMap
# - Wrong Llama Stack URL
# - Image pull errors (check BuildConfig)
```

### RemoteMCPServer not accepted

```bash
# Check RemoteMCPServer status
oc get remotemcpserver llamastack-rag -n mschimun
oc describe remotemcpserver llamastack-rag -n mschimun

# Status should show:
# - ACCEPTED: True
# - Discovered tools: search_knowledge_base

# Common issues:
# - Wrong URL (must end with /mcp for streamable-http)
# - Service not accessible from kagent namespace
# - Pod not ready (check health probes)
```

### Search returns no results

```bash
# Test Llama Stack directly
oc port-forward -n mschimun svc/llama-stack-service 8321:8321 &

# Test search endpoint
curl -X POST http://localhost:8321/v1/vector_stores/vs_.../search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "max_num_results": 3,
    "search_mode": "vector"
  }' | jq .

# Check vector store has documents
curl http://localhost:8321/v1/vector_stores | jq .
```

### Agent doesn't use the tool

Check agent's system message includes RAG instructions:

```yaml
systemMessage: |
  IMPORTANT: When answering questions about X, Y, Z,
  ALWAYS use the search_knowledge_base tool first.
```

## Implementation Details

### Why streamable-http?

kagent's MCP client uses `POST` requests to communicate with MCP servers. FastMCP's SSE transport expects `GET` requests and responds with Server-Sent Events. The `streamable-http` transport supports `POST` requests and is compatible with kagent's MCP implementation.

### Why ConfigMap instead of X-headers?

We initially tried using X-headers to pass configuration (more flexible, per-request config), but MCP frameworks don't expose HTTP headers to tool functions. ConfigMap-based environment variables are the standard Kubernetes pattern and work reliably.

### Why not kagent's Memory CRD?

kagent has a `Memory` CRD for RAG, but:
- Only supports Pinecone currently
- No Python ADK implementation for custom memory providers
- Would require contributing to kagent (good long-term goal!)

This MCP approach works **today** with any MCP-compatible framework.

## Future Improvements

- [ ] **Streaming responses** - Stream chunks as they're found
- [ ] **Better metadata** - Include source URLs, timestamps, relevance scores
- [ ] **Query caching** - Cache frequent queries for faster responses
- [ ] **Multi-tenant auth** - Support per-agent Llama Stack tokens
- [ ] **Observability** - Export metrics (queries/sec, latency, cache hits)
- [ ] **kagent Memory Provider** - Contribute Llama Stack provider to kagent

## Related Documentation

- [Llama Stack Vector Store API](https://llama-stack.readthedocs.io/)
- [FastMCP Documentation](https://gofastmcp.com)
- [Model Context Protocol Spec](https://spec.modelcontextprotocol.io/)
- [kagent RemoteMCPServer CRD](https://kagent.dev/docs/tools/mcp-servers)

## License

See main repository LICENSE.
