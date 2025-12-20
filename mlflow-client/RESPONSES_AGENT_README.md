# Llamastack Agent Wrapper for MLflow

This directory contains a `ResponsesAgent` wrapper that wraps a Llamastack agent, following the same pattern as MLflow's LangGraph agent wrapper.

## Overview

The `LlamastackAgentWrapper` is a subclass of `mlflow.pyfunc.ResponsesAgent` that:
- Wraps a Llamastack agent using Llamastack's Agents API
- Can create new agents or use existing agents configured in Llamastack
- Supports tool registration (e.g., RAG tools)
- Handles chat completions and tool calling
- Provides automatic MLflow tracing
- Supports both streaming and non-streaming responses
- Integrates seamlessly with MLflow's model serving infrastructure

## Architecture

```
┌──────────────┐
│ User / API   │
└──────┬───────┘
       │
       │ POST /invocations
       ▼
┌──────────────────────────┐
│ MLflow Agent Server      │
│                          │
│  - /invocations endpoint │
│  - Agent serving         │
│  - Automatic tracing     │
└──────┬───────────────────┘
       │
       │ ResponsesAgent.predict()
       ▼
┌──────────────────────────┐
│ LlamastackAgentWrapper  │
│                          │
│  - Wraps Llamastack Agent│
│  - Request/response      │
│    conversion            │
└──────┬───────────────────┘
       │
       │ POST /v1/agents/{agent_id}/session/{session_id}/turn
       ▼
┌──────────────────────────┐
│ Llamastack Agents API    │
│                          │
│  - Agent execution       │
│  - Tool calling (RAG, etc)│
└──────┬───────────────────┘
       │
       │
       ▼
┌──────────────────────────┐
│ Llamastack Agent        │
│                          │
│  - Model inference       │
│  - Tool execution        │
└──────────────────────────┘
```

## Files

- **`llamastack_agent_wrapper_direct.py`** - Wraps a Llamastack agent using the Agents API (similar to LangGraph wrapper pattern)
- **`log_llamastack_agent_direct.py`** - Script to log the agent wrapper to MLflow

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables (optional, defaults shown):

```bash
export LLAMASTACK_BASE_URL="http://localhost:8321"
export LLAMASTACK_AGENT_ID=""  # Empty = create new agent, or provide existing agent ID
export LLAMASTACK_MODEL="ollama/llama3.2:1b"  # Model to use for agent
export LLAMASTACK_API_KEY="fake"
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MLFLOW_EXPERIMENT="llamastack-agent-wrapper-direct"
```

For Kubernetes/OpenShift deployments, use the service URL:

```bash
export LLAMASTACK_BASE_URL="http://llamastack-service.namespace.svc.cluster.local:8321"
```

## Usage

### 1. Log the Agent to MLflow

Log the agent wrapper to MLflow for serving:

```bash
python log_llamastack_agent_direct.py
```

This will:
- Create an MLflow run
- Log the agent wrapper as a model
- Register it in the MLflow model registry (if configured)
- Print instructions for serving

### 2. Serve the Agent

Serve the logged agent locally:

```bash
# Using the model URI from logging
mlflow models serve -m runs:/<run_id>/agent -p 5000

# Or using the registered model
mlflow models serve -m models:/llamastack-agent-wrapper-direct/latest -p 5000
```

### 3. Test the Agent

Test the agent locally (without serving):

```bash
python test_agent_with_tools.py local
```

Test the served agent:

```bash
# Start the server first (see step 2)
python test_agent_with_tools.py served http://localhost:5000
```

### 4. Send Requests to the Served Agent

Using Python:

```python
import requests

response = requests.post(
    "http://localhost:5000/invocations",
    json={
        "input": [
            {
                "role": "user",
                "content": "What is OpenShift?"
            }
        ]
    },
    headers={"Content-Type": "application/json"},
)

print(response.json())
```

Using curl:

```bash
curl -X POST http://localhost:5000/invocations \
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

## Configuration

The agent wrapper can be configured via:

1. **Environment variables** (recommended for deployment):
   - `LLAMASTACK_BASE_URL` - Base URL for Llamastack server (without /v1 suffix)
   - `LLAMASTACK_AGENT_ID` - ID of existing agent (empty = create new agent)
   - `LLAMASTACK_MODEL` - Model name to use for agent (defaults to agent_id if provided)
   - `LLAMASTACK_API_KEY` - API key (defaults to "fake" for Llamastack)

2. **Constructor parameters** (for programmatic use):
   ```python
   from llamastack_agent_wrapper_direct import LlamastackAgentWrapper
   from mlflow.models import set_model
   
   agent = LlamastackAgentWrapper(
       llamastack_base_url="http://localhost:8321",
       agent_id=None,  # None = create new agent
       api_key="fake",
       model="ollama/llama3.2:1b",
       tools=[  # Optional: register tools with agent
           {
               "name": "builtin::rag/knowledge_search",
               "args": {}
           }
       ]
   )
   set_model(agent)
   ```

## Agent Creation

The wrapper supports two modes:

1. **Use Existing Agent**: Set `LLAMASTACK_AGENT_ID` to an existing agent ID in Llamastack
2. **Create New Agent**: Leave `LLAMASTACK_AGENT_ID` empty or set to `None` - the wrapper will create a new agent via `POST /v1/agents` with the specified tools

## Tool Registration

To register tools with a new agent, pass them in the `tools` parameter:

```python
tools = [
    {
        "name": "builtin::rag/knowledge_search",
        "args": {
            "vector_db_ids": ["your-vector-db-id"]  # For RAG, create vector DB first
        }
    }
]
```

For RAG to work properly:
1. Create a vector DB: `POST /v1/vector-dbs` with documents
2. Get the `vector_db_id` from the response
3. Register RAG tool with `vector_db_ids` in the tool args

## Features

### Automatic MLflow Tracing

The agent automatically creates MLflow traces when processing requests. Traces include:
- Agent-level spans
- Request/response details
- Token usage information
- Latency metrics

### Tool Calling Support

The agent supports tool calling through Llamastack's Agents API. Tools registered with the agent (e.g., RAG) are automatically available.

### Streaming Support

The agent supports streaming responses via the `predict_stream` method:

```python
for event in agent.predict_stream(request):
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
```

## Troubleshooting

### Connection Errors

If you get connection errors, verify:
1. Llamastack server is running and accessible
2. The `LLAMASTACK_BASE_URL` is correct (without /v1 suffix)
3. Network connectivity (for Kubernetes, check service name and namespace)

### Agent Not Found

If the agent is not found:
1. Verify the agent ID matches what's configured in Llamastack
2. Check that the agent was created successfully (check logs)
3. Verify the `LLAMASTACK_AGENT_ID` environment variable

### Agents API Not Available

If the Agents API is not available, the wrapper falls back to chat completions API. Check:
1. Llamastack version supports Agents API
2. The endpoint `/v1/agents/{agent_id}/session/{session_id}/turn` is accessible
3. Check wrapper logs for fallback messages

### MLflow Serving Issues

If serving fails:
1. Ensure all dependencies are installed in the serving environment
2. Check that environment variables are set correctly
3. Verify MLflow can access the model artifacts

## Example: Full Workflow

```bash
# 1. Set environment variables
export LLAMASTACK_BASE_URL="http://localhost:8321"
export LLAMASTACK_AGENT_ID=""  # Create new agent
export LLAMASTACK_MODEL="ollama/llama3.2:1b"
export MLFLOW_TRACKING_URI="http://localhost:5000"

# 2. Log the agent wrapper
python log_llamastack_agent_direct.py

# 3. Serve the agent (in a separate terminal)
mlflow models serve -m models:/llamastack-agent-wrapper-direct/latest -p 5000

# 4. Test the served agent (in another terminal)
python test_agent_with_tools.py served http://localhost:5000
```

## Integration with Existing Infrastructure

This agent wrapper integrates with:
- **Llamastack**: Uses Agents API (`/v1/agents/{agent_id}/session/{session_id}/turn`)
- **MLflow**: Full tracking, serving, and tracing support
- **Kubernetes/OpenShift**: Can be deployed as a service

## Pattern: Wrapping Llamastack Agent

This wrapper follows the same pattern as MLflow's LangGraph agent wrapper:
- ResponsesAgent wraps the Llamastack agent
- Agent is instantiated directly and passed to `set_model()`
- Uses Llamastack's native agent capabilities (tool calling, multi-step reasoning)
- Similar to the pattern shown in the [MLflow documentation](https://mlflow.org/docs/3.5.1/genai/serving/responses-agent/#wrapping-a-langgraph-agent)

## Next Steps

- Add tool calling examples
- Implement multi-agent orchestration
- Add RAG capabilities with vector DB setup
- Create deployment YAMLs for Kubernetes/OpenShift
- Add support for more Llamastack agent features
