# cagent Hello World Agent

A simple cagent agent that demonstrates the complete multi-agent platform stack: cagent → Llama Stack → vLLM.

## Overview

This agent:
- Uses cagent's declarative YAML configuration
- Connects to Llama Stack for inference
- Uses the vLLM-served Qwen3-14B-AWQ model
- Demonstrates the foundation layer for multi-agent systems

## Files

- **`agent.yaml`** - cagent configuration template (uses NAMESPACE_PLACEHOLDER)
- **`Dockerfile`** - Container image definition for the agent
- **`buildconfig.yaml`** - OpenShift BuildConfig for cluster-based builds
- **`deployment.yaml`** - Kubernetes Deployment and Service manifests

## Configuration

The agent connects to Llama Stack via OpenAI-compatible API:
- **Endpoint:** `http://llama-stack-service.<namespace>.svc.cluster.local:8321/v1`
- **Model:** `vllm-inference-1/qwen3-14b-awq`
- **Max tokens:** 4096
- **Temperature:** 0.7

## Deployment

Deploy using the Makefile:

```bash
# Deploy complete stack (vLLM + Llama Stack + Agent)
make deploy NAMESPACE=my-namespace

# Or deploy agent only (if vLLM and Llama Stack already exist)
make build-agent NAMESPACE=my-namespace
make deploy-agent NAMESPACE=my-namespace

# Check status
make status NAMESPACE=my-namespace
```

## Testing the Agent

### From Within the Cluster

```bash
# Create a test pod
oc run test-curl --rm -i --restart=Never --image=curlimages/curl:latest -n my-namespace -- sh

# Inside the pod, run these commands:

# 1. Create a session
SESSION_RESPONSE=$(curl -s -X POST http://hello-agent.my-namespace.svc:8080/api/sessions \
  -H "Content-Type: application/json" \
  -d "{}")

# 2. Extract session ID
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Session ID: $SESSION_ID"

# 3. Send a message to the agent
curl -N -X POST "http://hello-agent.my-namespace.svc:8080/api/sessions/$SESSION_ID/agent/agent.yaml" \
  -H "Content-Type: application/json" \
  -d '[{"role": "user", "content": "Hello! Introduce yourself in one sentence."}]'
```

### From Your Local Machine

```bash
# 1. Port forward the agent service
oc port-forward -n my-namespace svc/hello-agent 8080:8080

# 2. In another terminal, create a session
SESSION_RESPONSE=$(curl -s -X POST http://localhost:8080/api/sessions \
  -H "Content-Type: application/json" \
  -d "{}")

SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Session ID: $SESSION_ID"

# 3. Send a message
curl -N -X POST "http://localhost:8080/api/sessions/$SESSION_ID/agent/agent.yaml" \
  -H "Content-Type: application/json" \
  -d '[{"role": "user", "content": "Say hello in 3 words."}]'
```

### Example Response

The agent streams responses as Server-Sent Events (SSE):

```
data: {"type":"user_message","message":"Hello! Introduce yourself in one sentence."}
data: {"type":"stream_started","session_id":"...","agent_name":"root"}
data: {"type":"agent_choice","content":"Hello","agent_name":"root"}
data: {"type":"agent_choice","content":"!","agent_name":"root"}
data: {"type":"agent_choice","content":" I","agent_name":"root"}
data: {"type":"agent_choice","content":"'m","agent_name":"root"}
...
data: {"type":"token_usage","usage":{"input_tokens":84,"output_tokens":197,"context_length":281}}
data: {"type":"stream_stopped","session_id":"...","agent_name":"root"}
```

**Complete response:** "Hello! I'm a friendly AI assistant powered by Llama Stack with vLLM backend, here to help you with any questions you may have."

## API Endpoints

The cagent API server exposes:

- `GET /api/ping` - Health check (`{"status":"ok"}`)
- `GET /api/agents` - List available agents
- `GET /api/sessions` - List all sessions
- `POST /api/sessions` - Create a new session (returns session object with ID)
- `GET /api/sessions/:id` - Get session details
- `POST /api/sessions/:id/agent/:agent` - Send message to agent (streaming SSE response)
- `DELETE /api/sessions/:id` - Delete a session
- `POST /api/sessions/:id/tools/toggle` - Toggle YOLO mode (auto-approve tools)

## Manual Build and Deploy

If you need to build and deploy manually without the Makefile:

```bash
# 1. Prepare agent configuration
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' agent.yaml > agent-build.yaml

# 2. Create BuildConfig
sed 's/NAMESPACE_PLACEHOLDER/my-namespace/g' buildconfig.yaml | oc apply -f -

# 3. Copy the prepared agent.yaml for build
cp agent-build.yaml agent.yaml

# 4. Start build
oc start-build hello-agent -n my-namespace --from-dir=. --follow

# 5. Get built image reference
AGENT_IMAGE=$(oc get imagestream hello-agent -n my-namespace -o jsonpath='{.status.tags[0].items[0].dockerImageReference}')

# 6. Deploy
sed "s/NAMESPACE_PLACEHOLDER/my-namespace/g" deployment.yaml | \
  sed "s|your-registry/hello-agent:v1|$AGENT_IMAGE|g" | oc apply -f -
```

## Troubleshooting

### Check agent logs
```bash
oc logs -n my-namespace -l app=hello-agent -c cagent
```

### Check image build status
```bash
oc get builds -n my-namespace
oc logs build/hello-agent-1 -n my-namespace
```

### Verify Llama Stack connectivity
```bash
oc exec -n my-namespace deployment/hello-agent -c cagent -- sh -c \
  'echo | nc -v llama-stack-service.my-namespace.svc.cluster.local 8321'
```

### Check agent is responding
```bash
oc exec -n my-namespace deployment/hello-agent -c cagent -- sh -c \
  'echo | nc -v localhost 8080'
```

## Next Steps

This hello world agent serves as a template for:
- Creating specialized agents (Jira, usage, finance agents)
- Building multi-agent orchestrators  
- Implementing the complete platform architecture

See [../docs/architecture-proposal.md](../docs/architecture-proposal.md) for the full multi-agent platform design.
