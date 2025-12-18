# kagent Hello World Agent

A kagent agent that demonstrates Kubernetes-native agent deployment using Llama Stack as the LLM backend.

## Overview

This agent:
- Uses kagent's Kubernetes CRD approach
- Connects to Llama Stack via OpenAI-compatible API
- Managed by kagent controller (automatic deployment)
- Exposes A2A protocol endpoint
- Can use MCP tools via kagent's ToolServer system

## Files

- **`modelconfig.yaml`** - ModelConfig CRD defining Llama Stack connection
- **`secret.yaml`** - Dummy secret (required by kagent but not used by Llama Stack)
- **`agent.yaml`** - Agent CRD defining the agent behavior

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

## Next Steps

- Test agent with questions about the platform
- Compare behavior with cagent agent
- Add MCP tools via ToolServer CRDs
- Explore kagent UI for management

