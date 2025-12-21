# Strategy Comparison: kagent + OTEL vs MLflow ResponsesAgent

## Goal

Build AI agents that achieve all three requirements:
1. **kagenti orchestration** - A2A protocol compliance for multi-agent workflows
2. **MLflow monitoring** - Traces, metrics, and experiment tracking
3. **Llama Stack backend** - LLM inference and RAG via vector stores

---

## Background: Key Components

### What is kagent?

kagent is a Kubernetes-native framework for deploying AI agents. It provides:
- **Custom Resource Definitions (CRDs)** for declarative agent configuration
- **Built-in A2A protocol support** for agent-to-agent communication
- **MCP tool integration** for connecting agents to external tools
- **OpenTelemetry (OTEL) tracing** built into its runtime

kagent has two deployment modes:
- **Declarative mode**: YAML-only configuration, kagent manages everything
- **BYO (Bring Your Own) mode**: Deploy your own container image

### What is kagenti?

kagenti is a framework-neutral orchestration platform that:
- Discovers agents via the **A2A protocol**
- Provides identity management (SPIRE), authentication (Keycloak), and service mesh (Istio)
- Routes requests to appropriate agents
- Does NOT require kagent - any A2A-compliant agent works

### What is MLflow ResponsesAgent?

MLflow's ResponsesAgent is a Python class for building AI agents with:
- **Automatic tracing** of all LLM calls and tool invocations
- **Structured request/response** handling
- **OpenAI-compatible API** support
- **Model registry** integration for versioning

### What is the A2A Protocol?

Agent-to-Agent (A2A) is Google's open protocol for agent communication. It requires:
- `GET /.well-known/agent.json` - Returns agent metadata (skills, capabilities)
- `POST /` - JSON-RPC endpoint for task execution
- Standard HTTP service on port 8080

---

## The Two Strategies

### Strategy A: kagent Declarative + OTEL to MLflow

Use kagent's built-in capabilities with OpenTelemetry forwarding traces to MLflow.

### Strategy B: MLflow ResponsesAgent + Custom A2A Wrapper

Build a custom container with MLflow ResponsesAgent, implementing A2A endpoints manually.

---

## Strategy A: kagent Declarative + OTEL

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Agent Pod (managed by kagent controller)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  kagent ADK Runtime                                      │  │
│  │  • A2A endpoints (auto-generated from CRD)               │  │
│  │  • MCP tool connections                                  │  │
│  │  • OpenTelemetry tracing (built-in)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
         │ OTLP (gRPC :4317)
         ↓
┌────────────────────────────────────────────────────────────────┐
│  OpenTelemetry Collector                                       │
│  • Receives traces from kagent                                 │
│  • Transforms and exports to MLflow                            │
└────────────────────────────────────────────────────────────────┘
         │ HTTP
         ↓
┌────────────────────┐     ┌─────────────────────┐
│  MLflow Tracking   │     │   Llama Stack       │
│  Server            │     │   • OpenAI API      │
└────────────────────┘     │   • Vector Store    │
                           └─────────────────────┘
```

### How It Works

1. **Agent Definition**: You create a kagent Agent CRD in YAML
2. **Deployment**: kagent controller creates Kubernetes Deployment, Service, ConfigMap
3. **A2A Endpoints**: kagent runtime automatically exposes `/.well-known/agent.json` and `POST /`
4. **LLM Calls**: Agent calls Llama Stack via OpenAI-compatible API (`/v1/chat/completions`)
5. **RAG**: Agent uses MCP tools to search vector stores (requires MCP server deployment)
6. **Tracing**: Built-in OTEL sends spans to collector, which forwards to MLflow

### Configuration

**Agent CRD with OTEL enabled:**

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: my-agent
  namespace: my-namespace
spec:
  type: Declarative
  description: "AI agent with MLflow tracing"
  
  declarative:
    # Reference to LLM configuration
    modelConfig: llama-stack-model
    
    # System prompt
    systemMessage: |
      You are a helpful AI assistant.
      Use the search tool for knowledge queries.
    
    # Enable OTEL tracing
    deployment:
      env:
        - name: OTEL_TRACING_ENABLED
          value: "true"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector:4317"
    
    # A2A configuration for kagenti discovery
    a2aConfig:
      skills:
        - id: answer
          name: answer
          description: Answer user questions
          tags: [qa, general]
    
    # MCP tools (RAG, external APIs)
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: vector-search-mcp
          toolNames: [search_knowledge_base]
```

**Model Configuration:**

```yaml
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: llama-stack-model
spec:
  provider: OpenAI
  model: my-model-name
  openAI:
    baseUrl: http://llama-stack-service:8321/v1
  apiKeySecret: llama-stack-key
  apiKeySecretKey: api-key
```

**OTEL Collector Configuration:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
    
    exporters:
      otlphttp:
        endpoint: http://mlflow-service:5000/api/2.0/mlflow/traces
        headers:
          Content-Type: application/json
    
    service:
      pipelines:
        traces:
          receivers: [otlp]
          exporters: [otlphttp]
```

### RAG Integration

Since kagent uses the OpenAI-compatible API (not Llama Stack's native Agents API), RAG requires an MCP bridge:

```
Agent → MCP Tool → Vector Store Search API → Results → Agent
```

The MCP server wraps Llama Stack's vector store search endpoint:
- Receives search query from agent
- Calls `POST /v1/vector_stores/{id}/search`
- Returns formatted results

### What You Get

| Feature | How It's Achieved |
|---------|-------------------|
| A2A Protocol | Auto-generated by kagent from `a2aConfig` |
| kagenti Discovery | `/.well-known/agent.json` exposed automatically |
| MLflow Tracing | OTEL traces forwarded via collector |
| LLM Integration | OpenAI-compatible API to Llama Stack |
| RAG | MCP server bridging to vector store |
| Deployment | kagent CRD → Kubernetes resources |

### Advantages

1. **Zero custom code** - Pure YAML configuration
2. **A2A built-in** - No protocol implementation needed
3. **Managed lifecycle** - kagent handles deployment, scaling, updates
4. **OTEL ready** - Just enable and configure endpoint
5. **MCP ecosystem** - Leverage existing MCP tools

### Limitations

1. **Indirect RAG** - Requires MCP wrapper, not native Llama Stack RAG tool
2. **OTEL trace format** - Standard spans, limited custom metadata
3. **Additional components** - Need OTEL Collector deployment
4. **Less control** - Can't customize agent logic beyond YAML
5. **kagent dependency** - Tied to kagent runtime versions

---

## Strategy B: MLflow ResponsesAgent + A2A Wrapper

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Custom Agent Container                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI A2A Server (custom implementation)              │  │
│  │  • GET /.well-known/agent.json                           │  │
│  │  • POST / (JSON-RPC handler)                             │  │
│  │  • GET /health                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                      │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MLflow ResponsesAgent                                   │  │
│  │  • Wraps Llama Stack client                              │  │
│  │  • @mlflow.trace decorators                              │  │
│  │  • predict() / predict_stream() methods                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                      │
│         ↓                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Llama Stack Client                                      │  │
│  │  • Creates agent with tools                              │  │
│  │  • Calls /v1/agents/{id}/session/{sid}/turn              │  │
│  │  • Native RAG tool support                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
         │ HTTP (direct)
         ↓
┌────────────────────┐     ┌─────────────────────┐
│  MLflow Tracking   │     │   Llama Stack       │
│  Server            │     │   • Agents API      │
└────────────────────┘     │   • builtin::rag    │
                           │   • Vector Store    │
                           └─────────────────────┘
```

### How It Works

1. **Agent Creation**: Python code creates a Llama Stack agent with RAG tool configured
2. **MLflow Wrapper**: ResponsesAgent class wraps the Llama Stack client
3. **A2A Bridge**: FastAPI server exposes A2A-compliant endpoints
4. **Request Flow**: A2A request → translate → MLflow agent → Llama Stack → response → translate back
5. **Tracing**: MLflow automatically traces all operations via decorators

### Implementation Components

**A2A Server (FastAPI):**

```python
from fastapi import FastAPI
from pydantic import BaseModel
import mlflow
import os
import json
import uuid

app = FastAPI()

# Configuration from environment variables
AGENT_NAME = os.getenv("AGENT_NAME", "my-agent")
AGENT_DESCRIPTION = os.getenv("AGENT_DESCRIPTION", "")
AGENT_SKILLS = json.loads(os.getenv("AGENT_SKILLS", "[]"))
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

# Import the MLflow agent (defined separately)
from agent_wrapper import agent

@app.get("/.well-known/agent.json")
def agent_card():
    """
    A2A Agent Card - Returns agent metadata for discovery.
    kagenti and other A2A clients use this to understand agent capabilities.
    """
    return {
        "name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "protocolVersion": "0.3.0",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": AGENT_SKILLS,
        "url": f"http://{AGENT_NAME}.{NAMESPACE}.svc:8080",
        "preferredTransport": "JSONRPC"
    }

@app.post("/")
@mlflow.trace(name="a2a_request")
def a2a_handler(request: dict):
    """
    A2A JSON-RPC endpoint - Handles task execution requests.
    Translates between A2A protocol and MLflow ResponsesAgent format.
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method in ["sessions/create", "tasks/send"]:
        # Extract messages from A2A format
        messages = params.get("messages", [])
        
        # Convert to MLflow ResponsesAgent format
        mlflow_request = {
            "input": messages
        }
        
        # Call MLflow agent (tracing happens automatically)
        with mlflow.start_span(name="agent_execution"):
            result = agent.predict(mlflow_request)
        
        # Convert back to A2A format
        return {
            "jsonrpc": "2.0",
            "result": {
                "session_id": str(uuid.uuid4()),
                "status": "completed",
                "messages": result.get("output", [])
            },
            "id": request_id
        }
    
    # Unknown method
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        },
        "id": request_id
    }

@app.get("/health")
def health():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy"}

@app.post("/invocations")
@mlflow.trace(name="mlflow_direct")
def mlflow_invocations(request: dict):
    """
    MLflow-native endpoint for direct access.
    Bypasses A2A translation for testing or direct integration.
    """
    return agent.predict(request)
```

**MLflow ResponsesAgent Wrapper:**

```python
from mlflow.pyfunc import ResponsesAgent, set_model
from mlflow.entities import SpanType
import mlflow
import httpx
import os

class LlamaStackAgentWrapper(ResponsesAgent):
    """
    MLflow ResponsesAgent that wraps Llama Stack's Agents API.
    Provides automatic tracing and structured request/response handling.
    """
    
    def __init__(self):
        super().__init__()
        
        # Configuration from environment
        self.base_url = os.getenv("LLAMASTACK_BASE_URL", "http://localhost:8321")
        self.model = os.getenv("LLAMASTACK_MODEL", "default-model")
        self.vector_store_id = os.getenv("VECTOR_STORE_ID")
        self.api_key = os.getenv("LLAMASTACK_API_KEY", "")
        
        # HTTP client
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            timeout=60.0
        )
        
        # Create agent in Llama Stack with tools
        self.agent_id = self._create_agent()
    
    def _create_agent(self) -> str:
        """Create an agent in Llama Stack with configured tools."""
        tools = []
        
        # Add RAG tool if vector store configured
        if self.vector_store_id:
            tools.append({
                "name": "builtin::rag/knowledge_search",
                "args": {
                    "vector_db_ids": [self.vector_store_id]
                }
            })
        
        # Create agent
        response = self.client.post("/v1/agents", json={
            "agent_config": {
                "model": self.model,
                "instructions": os.getenv("AGENT_INSTRUCTIONS", "You are a helpful assistant."),
                "tools": tools,
                "enable_session_persistence": False
            }
        })
        response.raise_for_status()
        return response.json()["agent_id"]
    
    @mlflow.trace(span_type=SpanType.AGENT)
    def predict(self, request: dict) -> dict:
        """
        Execute agent turn with full MLflow tracing.
        
        Args:
            request: {"input": [{"role": "user", "content": "..."}]}
        
        Returns:
            {"output": [{"type": "text", "text": "..."}]}
        """
        messages = request.get("input", [])
        
        # Create session
        session_response = self.client.post(
            f"/v1/agents/{self.agent_id}/session",
            json={"session_name": f"session-{mlflow.active_run().info.run_id}"}
        )
        session_id = session_response.json()["session_id"]
        
        # Execute turn
        with mlflow.start_span(name="llama_stack_turn", span_type=SpanType.LLM):
            turn_response = self.client.post(
                f"/v1/agents/{self.agent_id}/session/{session_id}/turn",
                json={"messages": messages}
            )
            result = turn_response.json()
        
        # Extract response
        output = []
        for event in result.get("events", []):
            if event.get("type") == "turn_complete":
                content = event.get("turn", {}).get("output_message", {}).get("content", "")
                output.append({"type": "text", "text": content})
        
        return {"output": output}

# Instantiate and register with MLflow
agent = LlamaStackAgentWrapper()
set_model(agent)
```

**Dockerfile:**

```dockerfile
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY a2a_server.py .
COPY agent_wrapper.py .

# Expose A2A port
EXPOSE 8080

# Start server
CMD ["uvicorn", "a2a_server:app", "--host", "0.0.0.0", "--port", "8080"]
```

**requirements.txt:**

```
fastapi>=0.100.0
uvicorn>=0.23.0
mlflow>=2.10.0
httpx>=0.27.0
pydantic>=2.0.0
```

### Deployment Options

**Option 1: kagent BYO Mode**

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: mlflow-agent
spec:
  type: BYO
  description: "MLflow ResponsesAgent with native RAG"
  
  byo:
    deployment:
      image: my-registry/mlflow-agent:latest
      replicas: 1
      
      env:
        # Llama Stack connection
        - name: LLAMASTACK_BASE_URL
          value: "http://llama-stack-service:8321"
        - name: LLAMASTACK_MODEL
          value: "my-model-name"
        - name: VECTOR_STORE_ID
          valueFrom:
            configMapKeyRef:
              name: vectorstore-config
              key: VECTOR_STORE_ID
        
        # MLflow connection
        - name: MLFLOW_TRACKING_URI
          value: "http://mlflow-service:5000"
        
        # A2A configuration
        - name: AGENT_NAME
          value: "mlflow-agent"
        - name: AGENT_DESCRIPTION
          value: "AI agent with native RAG and MLflow tracing"
        - name: AGENT_SKILLS
          value: '[{"id":"answer","name":"answer","description":"Answer questions using knowledge base"}]'
      
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
```

**Option 2: Plain Kubernetes Deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mlflow-agent
  template:
    metadata:
      labels:
        app: mlflow-agent
    spec:
      containers:
        - name: agent
          image: my-registry/mlflow-agent:latest
          ports:
            - containerPort: 8080
          env:
            # Same environment variables as above
            - name: LLAMASTACK_BASE_URL
              value: "http://llama-stack-service:8321"
            # ... etc
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: mlflow-agent
spec:
  selector:
    app: mlflow-agent
  ports:
    - port: 8080
      targetPort: 8080
```

### What You Get

| Feature | How It's Achieved |
|---------|-------------------|
| A2A Protocol | Custom FastAPI implementation |
| kagenti Discovery | `/.well-known/agent.json` endpoint |
| MLflow Tracing | Native `@mlflow.trace` decorators |
| LLM Integration | Llama Stack Agents API directly |
| RAG | Native `builtin::rag/knowledge_search` tool |
| Custom Metadata | Full control over MLflow tags/metrics |

### Advantages

1. **Native MLflow tracing** - Full control over spans, tags, and metrics
2. **Native Llama Stack RAG** - Direct use of `builtin::rag` tool
3. **Llama Stack Agents API** - Access to all features (tools, sessions, streaming)
4. **Single container** - No sidecar or collector needed
5. **Rich observability** - Custom MLflow experiments and model registry
6. **Flexible deployment** - Works with or without kagent

### Limitations

1. **Custom code required** - ~200-300 lines of Python
2. **A2A implementation** - Must handle protocol correctly
3. **Build pipeline** - Need Dockerfile and image registry
4. **Maintenance burden** - Code updates when APIs change
5. **Testing complexity** - Multiple layers to debug

---

## MLflow-Specific Features

This section details MLflow capabilities available in Strategy B that are not present in Strategy A's OTEL-based approach.

### 1. Experiment Tracking

MLflow provides automatic logging of parameters, metrics, and artifacts for each agent run.

**Strategy B (MLflow ResponsesAgent):**

```python
# Automatic logging with MLflow
mlflow.log_param("model_name", "qwen3-14b")
mlflow.log_param("temperature", 0.7)
mlflow.log_param("system_prompt", system_message)
mlflow.log_param("tools", ["search_knowledge_base", "github"])
mlflow.log_metric("total_tokens", 1234)
mlflow.log_metric("latency_seconds", 2.5)
mlflow.log_metric("retrieval_score", 0.92)
```

**Strategy A (kagent + OTEL):**

OTEL provides spans with timing information. Parameter logging and metric aggregation are not included.

### 2. Agent as Artifact and Model Registry

MLflow can store the agent itself as a versioned artifact, enabling reproducibility and rollback.

**Strategy B (MLflow ResponsesAgent):**

```python
# Log agent as versioned artifact
mlflow.pyfunc.log_model(
    artifact_path="agent",
    python_model=my_agent,
    signature=signature
)

# Later: reload exact agent version
agent_v3 = mlflow.pyfunc.load_model("models:/my-agent/3")

# Model lifecycle stages
# Dev (v1, v2) → Staging (v3) → Production (v4)
```

**Strategy A (kagent + OTEL):**

Agent versioning is managed through:
- Git tags for YAML definitions
- Container image tags
- Kubernetes labels

No MLflow model registry integration.

### 3. LLM Evaluations

MLflow provides built-in evaluators for assessing agent response quality.

**Strategy B (MLflow ResponsesAgent):**

```python
# Built-in evaluation
results = mlflow.evaluate(
    model=agent,
    data=eval_dataset,
    evaluators=[
        "answer_relevance",    # Is answer relevant to question?
        "faithfulness",        # Does answer match retrieved context?
        "toxicity",            # Is response safe?
        "answer_correctness"   # Is answer factually correct?
    ]
)

# Access evaluation scores
print(results.metrics)
# {'answer_relevance': 0.92, 'faithfulness': 0.88, 'toxicity': 0.01, ...}
```

**Strategy A (kagent + OTEL):**

No built-in evaluation. Options include:
- Building a custom evaluation pipeline
- Calling an external evaluation service
- Manually logging results to a separate system

### 4. Input/Output Logging

MLflow automatically captures full request and response data for each run.

**Strategy B (MLflow ResponsesAgent):**

```
Each MLflow run captures:
├── inputs/
│   ├── user_message.txt
│   └── conversation_history.json
├── outputs/
│   ├── agent_response.txt
│   └── tool_calls.json
└── artifacts/
    └── retrieved_context.json
```

**Strategy A (kagent + OTEL):**

```
OTEL traces capture:
├── spans (timing information)
│   └── attributes (query text, result count)
└── No full input/output storage
```

### 5. Token Usage Tracking

**Strategy B (MLflow ResponsesAgent):**

```python
# Automatic token tracking
mlflow.log_metric("prompt_tokens", response.usage.prompt_tokens)
mlflow.log_metric("completion_tokens", response.usage.completion_tokens)
mlflow.log_metric("total_tokens", response.usage.total_tokens)
mlflow.log_metric("cost_usd", calculate_cost(response.usage))
```

**Strategy A (kagent + OTEL):**

Token usage is not automatically tracked. Would require custom instrumentation in the LLM provider or MCP tools.

### Feature Availability Summary

| MLflow Feature | Strategy A (OTEL) | Strategy B (ResponsesAgent) |
|----------------|-------------------|----------------------------|
| Distributed Tracing | ✅ Via OTEL | ✅ Native |
| Experiment Tracking | ❌ Not available | ✅ Automatic |
| Parameter Logging | ❌ Not available | ✅ Automatic |
| Metric Logging | ❌ Not available | ✅ Automatic |
| Agent Versioning | ❌ Git/K8s only | ✅ Model Registry |
| Model Lifecycle (Dev→Prod) | ❌ Not available | ✅ Built-in |
| LLM Evaluations | ❌ External only | ✅ Built-in |
| Input/Output Logs | ❌ Limited | ✅ Automatic |
| Token Usage | ❌ Not available | ✅ Automatic |

---

## Side-by-Side Comparison

### Complexity Analysis

| Dimension | Strategy A: kagent + OTEL | Strategy B: MLflow ResponsesAgent |
|-----------|---------------------------|-----------------------------------|
| **Lines of Code** | 0 (YAML only) | ~200-300 Python |
| **New Components** | OTEL Collector | Custom container image |
| **Build Pipeline** | None | Dockerfile + registry |
| **Configuration** | kagent CRD | Container env vars |
| **A2A Implementation** | Built-in (kagent) | Custom (FastAPI) |
| **MLflow Integration** | Via OTEL export | Native decorators |

### Feature Comparison

| Feature | Strategy A | Strategy B |
|---------|------------|------------|
| **A2A Protocol** | ✅ Automatic | ⚠️ Manual implementation |
| **kagenti Compatible** | ✅ Yes | ✅ Yes |
| **MLflow Tracing** | ⚠️ OTEL-based | ✅ Native |
| **Experiment Tracking** | ❌ Not available | ✅ Automatic |
| **Model Registry** | ❌ Not available | ✅ Built-in |
| **LLM Evaluations** | ❌ External only | ✅ Built-in |
| **Trace Detail** | Basic spans | Full control |
| **Custom Metrics** | Limited | ✅ Full MLflow API |
| **Token Usage** | ❌ Not available | ✅ Automatic |
| **Input/Output Logs** | ❌ Limited | ✅ Full |
| **Llama Stack RAG** | Via MCP wrapper | ✅ Native builtin::rag |
| **MCP Tools** | ✅ Built-in support | ⚠️ Manual integration |
| **Image Reuse** | ✅ Same kagent image | ✅ Configurable via env |
| **Deployment Method** | kagent CRD | CRD or plain K8s |

### Operational Comparison

| Aspect | Strategy A | Strategy B |
|--------|------------|------------|
| **Initial Setup Time** | 1-2 days | 3-5 days |
| **Debug Difficulty** | Low | Medium |
| **Component Count** | 3 (Agent + Collector + MLflow) | 2 (Agent + MLflow) |
| **Maintenance Effort** | Low (YAML updates) | Medium (code + YAML) |
| **Flexibility** | Medium | High |
| **Production Readiness** | High | Medium (needs testing) |

### Use Case Alignment

| Use Case | Strategy A | Strategy B |
|----------|------------|------------|
| Quick prototyping | ✅ | ⚠️ |
| Minimal custom code | ✅ | ❌ |
| Rich MLflow metadata | ❌ | ✅ |
| Native Llama Stack RAG | ❌ | ✅ |
| Custom trace logic | ❌ | ✅ |
| Complex agent logic | ⚠️ | ✅ |
| Managed lifecycle | ✅ | ⚠️ |
| Maximum control | ❌ | ✅ |
| MCP-based tools | ✅ | ⚠️ |
| Model versioning | ❌ | ✅ |
| LLM evaluation | ❌ | ✅ |

---

## Migration Path

Migration from Strategy A to Strategy B is possible without disrupting kagenti:

1. **Phase 1**: Deploy with kagent + OTEL
2. **Phase 2**: Evaluate trace quality and RAG performance
3. **Phase 3**: Build custom container with MLflow ResponsesAgent
4. **Phase 4**: Deploy new container with same A2A interface
5. **Result**: kagenti sees no change; both strategies expose identical A2A interfaces

---

## Summary

| Criteria | Strategy A | Strategy B |
|----------|------------|------------|
| Time to Deploy | 1-2 days | 3-5 days |
| Code Complexity | None (YAML only) | ~250 LOC Python |
| A2A Protocol | Built-in | Manual |
| MLflow Tracing | OTEL-based | Native |
| Experiment Tracking | Not available | Full |
| Model Registry | Not available | Full |
| LLM Evaluations | Not available | Built-in |
| RAG Integration | MCP wrapper | Native Llama Stack |
| MCP Tools | Built-in | Manual integration |
| Maintenance | Low | Medium |
| Flexibility | Medium | High |
| kagenti Compatible | Yes | Yes |

### Key Differences

**Strategy A (kagent + OTEL)**:
- Zero custom code, YAML-only configuration
- OTEL-level distributed tracing
- No MLflow experiment tracking, model registry, or evaluations
- RAG via MCP wrapper to vector store

**Strategy B (MLflow ResponsesAgent)**:
- Requires ~200-300 lines of Python code
- Full MLflow feature set (experiments, registry, evaluations)
- Native Llama Stack RAG with `builtin::rag` tool
- Custom A2A implementation required

**Both strategies**:
- Are compatible with kagenti orchestration
- Expose identical A2A protocol interfaces
- Can be deployed on Kubernetes
