# kagent Hello World Agent

A kagent agent that demonstrates Kubernetes-native agent deployment using Llama Stack as the LLM backend, with RAG via custom MCP and integration with kagenti for multi-agent orchestration.

## Overview

This agent:
- Uses kagent's Kubernetes CRD approach (`kagent.dev/v1alpha2`)
- Connects to Llama Stack via OpenAI-compatible API
- Managed by kagent controller (automatic deployment)
- Exposes A2A protocol endpoint on port 8080
- Uses RAG via custom `vector-search-mcp` (Llama Stack vector store)
- Integrates with GitHub via MCP tools
- Can be discovered and managed by kagenti-ui

## Files

| File | Description |
|------|-------------|
| `modelconfig.yaml` | ModelConfig CRD defining Llama Stack connection |
| `secret.yaml` | Dummy secret (required by kagent but not used by Llama Stack) |
| `agent.yaml` | Agent CRD defining the agent behavior with A2A config |
| `vector-search-mcpserver.yaml` | RemoteMCPServer for RAG via Llama Stack |
| `github-mcpserver.yaml` | RemoteMCPServer for GitHub integration |
| `RAG-AND-MCP.md` | Documentation on RAG and MCP learnings |

## Key Difference from cagent

**cagent:**
- Manual: Build image → Create deployment → Deploy
- Custom runtime
- Direct MCP calls

**kagent:**
- Declarative: Apply CRD → Controller handles everything
- ADK engine
- Native Kubernetes resources

## Deployment

```bash
# Deploy to a namespace
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' secret.yaml | oc apply -f -
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' modelconfig.yaml | oc apply -f -
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' agent.yaml | oc apply -f -

# Check status
oc get agent hello-agent -n my-namespace
oc get pods -n my-namespace -l kagent.dev/agent=hello-agent
```

## Testing

### Via kubectl/oc

```bash
# Get agent status
oc get agent hello-agent -n my-namespace -o yaml

# Check agent logs
oc logs -n my-namespace -l kagent.dev/agent=hello-agent

# View agent service
oc get svc -n my-namespace -l kagent.dev/agent=hello-agent
```

### Via A2A Protocol

kagent agents expose A2A protocol endpoints:

```bash
# Get agent card
curl http://hello-agent.my-namespace.svc:8080/.well-known/agent.json

# Send task
curl -X POST http://hello-agent.my-namespace.svc:8080/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello! What is kagent?"}'
```

### Via kagent CLI

If kagent CLI is available:

```bash
kagent chat hello-agent -n my-namespace
```

## Configuration

### Model Connection

The agent uses:
- **Provider:** OpenAI (with custom baseURL)
- **Endpoint:** `http://llama-stack-service.<namespace>.svc.cluster.local:8321/v1`
- **Model:** `vllm-inference-1/qwen3-14b-awq`

### Resources Created by kagent Controller

When you apply the Agent CRD, kagent controller automatically creates:
- Deployment (runs the ADK engine with your agent)
- Service (exposes A2A protocol)
- ConfigMaps (agent configuration)
- Any other required resources

## Architecture

```
User/System
    ↓ (A2A Protocol)
kagent Agent Pod (ADK Engine)
    ↓ (OpenAI API)
Llama Stack
    ↓
vLLM Model
```

## MCP Tools

kagent has built-in MCP tools via ToolServers:
- Kubernetes operations
- Helm charts
- Istio service mesh
- Prometheus metrics
- Grafana dashboards
- And more

To add MCP tools, create ToolServer CRDs (not shown in this hello-world example).

## Troubleshooting

### Agent not starting

```bash
# Check agent status
oc describe agent hello-agent -n my-namespace

# Check controller logs
oc logs -n kagent deployment/kagent-controller

# Check agent pod logs
oc logs -n my-namespace -l kagent.dev/agent=hello-agent
```

### Model connection issues

```bash
# Verify Llama Stack is accessible
oc exec -n my-namespace deployment/hello-agent -- \
  curl -s http://llama-stack-service.my-namespace.svc.cluster.local:8321/v1/models
```

## Comparison with cagent

**See:** `../cagent-helloworld/RAG-AND-MCP.md` for detailed comparison.

**Summary:**
- **cagent:** Container-based, custom runtime, manual deployment
- **kagent:** CRD-based, ADK engine, automatic deployment
- **Both:** Can connect to Llama Stack for LLM inference

## Kagenti Integration

### Overview

kagent (`kagent.dev`) and kagenti (`agent.kagenti.dev`) are two different systems:

| System | CRD API Group | Default Port | UI |
|--------|---------------|--------------|-----|
| **kagent** | `kagent.dev/v1alpha2` | 8080 | kagent-ui |
| **kagenti** | `agent.kagenti.dev/v1alpha1` | 8000 | kagenti-ui |

Both support A2A protocol, but kagenti-ui expects agents on port 8000 while kagent uses port 8080.

### Making kagent Agent Discoverable in kagenti-ui

To make a `kagent.dev` agent visible in kagenti-ui:

#### Step 1: Label the Namespace

```bash
# kagenti-ui only shows namespaces with this label
oc label namespace mschimun kagenti-enabled=true
```

#### Step 2: Label the Agent

Add the `kagenti.io/type: agent` label to your kagent agent:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: hello-kagent
  namespace: mschimun
  labels:
    app: kagent-helloworld
    kagenti.io/type: agent  # Required for kagenti discovery
```

#### Step 3: Create Port 8000 Service (Optional)

If you want kagenti-ui to interact with the agent (not just list it), create a service alias on port 8000:

```yaml
# File: kagenti-service-alias.yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-kagent-kagenti  # Different name to avoid conflicts
  namespace: mschimun
  labels:
    app: kagent
    kagent: hello-kagent
    kagenti.io/type: agent
spec:
  selector:
    app: kagent
    kagent: hello-kagent
  ports:
    - name: http
      protocol: TCP
      port: 8000        # kagenti-ui expects this
      targetPort: 8080  # kagent runs on this
```

#### Step 4: Create agent.kagenti.dev Wrapper (Advanced)

For full kagenti-operator integration, create a wrapper resource:

```yaml
# File: hello-kagent-kagenti-agent.yaml
apiVersion: agent.kagenti.dev/v1alpha1
kind: Agent
metadata:
  name: hello-kagent
  namespace: mschimun
  labels:
    kagenti.io/type: agent
    kagenti.io/agent-protocol: a2a
    kagenti.io/framework: kagent
    app.kubernetes.io/name: hello-kagent
spec:
  replicas: 0  # Don't deploy new pods, use existing kagent pods
  imageSource:
    image: "cr.kagent.dev/kagent-dev/kagent/app:0.7.7"
  servicePorts:
    - port: 8000
      targetPort: 8080
      protocol: TCP
      name: http
  podTemplateSpec:
    spec:
      containers:
        - name: agent
          image: "cr.kagent.dev/kagent-dev/kagent/app:0.7.7"
          ports:
            - containerPort: 8080
```

Then patch the created service to point to existing kagent pods:

```bash
oc patch svc hello-kagent -n mschimun --type='json' -p='[
  {"op": "replace", "path": "/spec/selector", "value": {"app": "kagent", "kagent": "hello-kagent"}}
]'
```

### Two UI Options

| UI | URL | Best For |
|----|-----|----------|
| **kagent-ui** | `https://kagent-ui-kagent.apps.rosa.<cluster>` | Native kagent.dev agents |
| **kagenti-ui** | `https://kagenti-ui-<namespace>.apps.rosa.<cluster>` | Multi-framework orchestration |

### Direct Access (Recommended for Testing)

```bash
# Port forward to kagent agent
oc port-forward -n mschimun svc/hello-kagent 8082:8080

# Get agent card
curl http://localhost:8082/.well-known/agent.json | jq

# Send A2A message
curl -X POST http://localhost:8082/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello!"}]
      }
    },
    "id": 1
  }'
```

## Next Steps

- Test agent with questions about the platform
- Compare behavior with cagent agent
- Add MCP tools via ToolServer CRDs
- Explore kagent UI for management
- Integrate with kagenti for multi-agent orchestration

