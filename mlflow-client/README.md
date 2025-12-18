# Kagent MLflow Logger

A Python client for sending questions to Kagent and logging the results to MLflow.

## Architecture

This repository implements **Pattern 1** for integrating **MLflow** with **kagent agents backed by Llama Stack (LLS)**.

In this pattern, MLflow is used strictly as an **out-of-band observability and experiment tracking sink**. It is **not** part of the live inference path.

**Core idea:**
> **Live path:** Client → kagent (A2A) → Llama Stack → response  
> **Observability path (after response):** Client / API → MLflow

This keeps the system fast, robust, and production-safe.

### Architecture Diagram

```
┌──────────────┐
│ Client / CLI │
│ (local, UI,  │
│  or API)     │
└──────┬───────┘
       │
       │ JSON-RPC (A2A)
       ▼
┌──────────────────────────┐
│ kagent Agent             │
│ (e.g. rh-analyze-simple) │
│                          │
│  - Agent lifecycle       │
│  - A2A endpoint          │
└──────┬───────────────────┘
       │
       │ OpenAI-compatible /v1
       ▼
┌──────────────────────────┐
│ Llama Stack (LLS)        │
│                          │
│  - Model abstraction     │
│  - (Future) RAG, tools   │
└──────────────────────────┘

(out-of-band, after response)
       │
       ▼
┌──────────────────────────┐
│ MLflow Tracking Server   │
│                          │
│  - Params / metrics      │
│  - Artifacts             │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Storage                  │
│                          │
│  - Postgres (metadata)   │
│  - MinIO (artifacts)     │
└──────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns:** The live inference path (kagent → Llama Stack) is completely independent from the observability path (MLflow logging).

2. **Non-Blocking:** MLflow logging happens asynchronously after the response is received, ensuring it doesn't impact response latency.

3. **Observability Focus:** MLflow captures metrics, parameters, and artifacts for analysis, debugging, and optimization without affecting production performance.

4. **Storage Backend:** 
   - **PostgreSQL** stores MLflow metadata (runs, experiments, metrics, parameters)
   - **MinIO** (S3-compatible) stores artifacts (question/answer text files, JSON responses)

---

## Pattern 2: MLflow Agent Server with ResponsesAgent (TODO)

> **Status:** This pattern is planned but not yet implemented. See TODO items below.

### Overview

**Pattern 2** uses **MLflow Agent Server** to host the agent logic directly, replacing the kagent deployment. The agent is implemented as an MLflow `ResponsesAgent` subclass, which provides built-in tracing, tool calling, and OpenAI Responses API compatibility.

**Core idea:**
> **Live path:** User/API → MLflow Agent Server (`/invocations`) → `ResponsesAgent.predict()` → Llama Stack (`/v1`) → response  
> **Tracing:** MLflow traces recorded automatically during execution

This pattern provides tighter integration with MLflow's observability features and leverages MLflow's native agent serving capabilities.

### Architecture Diagram

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
│ ResponsesAgent           │
│ (Your Implementation)    │
│                          │
│  - predict(request)      │
│  - Tool calling          │
│  - Chat history mgmt     │
│  - Token usage tracking  │
│  - Multi-agent support   │
└──────┬───────────────────┘
       │
       │ OpenAI-compatible /v1
       ▼
┌──────────────────────────┐
│ Llama Stack (LLS)        │
│                          │
│  - Model abstraction     │
│  - (Future) RAG, tools   │
└──────────────────────────┘
       │
       │ response
       ▼
┌──────────────────────────┐
│ MLflow Traces            │
│ (Automatic)              │
│                          │
│  - Spans for each step   │
│  - Function calls        │
│  - Token usage           │
└──────────────────────────┘
```

### ResponsesAgent Implementation

With Pattern 2, we implement an agent class by:

1. **Subclassing `mlflow.pyfunc.ResponsesAgent`:**
   ```python
   import mlflow
   from mlflow.pyfunc import ResponsesAgent, ResponsesAgentResponse
   
   class MyAgent(ResponsesAgent):
       def predict(self, request) -> ResponsesAgentResponse:
           # Your agent logic here
           return ResponsesAgentResponse(...)
   ```

2. **Implementing `predict(request) -> ResponsesAgentResponse`:**
   - Process the incoming request
   - Call Llama Stack via OpenAI-compatible `/v1` endpoint
   - Return structured output items (text items, function-call items, etc.)

3. **Using MLflow Tracing:**
   - Decorate methods with `@mlflow.trace` for automatic span creation
   - Traces are recorded automatically during execution
   - No manual logging required

### ResponsesAgent Features

The `ResponsesAgent` class provides built-in support for:

- **Tool Calling + Function Execution:** Native support for function/tool calling patterns
- **Chat History Management:** Automatic conversation context handling
- **Token Usage Tracking:** Built-in token counting and reporting
- **Multi-Agent Support:** Orchestrate multiple agents in a single flow
- **OpenAI Responses API Compatibility:** Compatible with OpenAI's Responses API format
- **MLflow Tracking/Serving Integration:** Seamless integration with MLflow's tracking and serving infrastructure

### Where Llama Stack Fits

Llama Stack maintains the same role as in Pattern 1:

- **OpenAI-compatible model API** (`/v1`) that your agent calls for completions
- **Future capabilities:** Retrieval, tools, and other advanced features

**Key Difference from Pattern 1:**

| Aspect | Pattern 1 | Pattern 2 |
|--------|-----------|-----------|
| Agent Hosting | kagent agent deployment | MLflow Agent Server |
| Agent Implementation | kagent agent config | `ResponsesAgent` subclass |
| Observability | Out-of-band logging | Built-in automatic tracing |
| API Endpoint | kagent A2A endpoint | MLflow `/invocations` |

### TODO: Pattern 2 Implementation

- [ ] Create `ResponsesAgent` implementation example
- [ ] Set up MLflow Agent Server deployment configuration
- [ ] Implement Llama Stack integration in `ResponsesAgent.predict()`
- [ ] Add tracing decorators and span instrumentation
- [ ] Create deployment YAMLs for MLflow Agent Server
- [ ] Add example client code for calling `/invocations` endpoint
- [ ] Document tool calling and function execution patterns
- [ ] Add multi-agent orchestration examples
- [ ] Update this README with working examples

---

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

Or use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run with a default question:

```bash
python kagent_mlflow_logger.py
```

Run with a custom question:

```bash
python kagent_mlflow_logger.py "What is Kubernetes?"
```

### Environment Variables

You can configure the script using environment variables:

```bash
export MLFLOW_TRACKING_URI="http://localhost:5000"
export A2A_URL="http://localhost:8083/api/a2a/kagent/rh-analyze-simple/"
export MLFLOW_EXPERIMENT="rh-analyze-mvp"

# MinIO/S3 configuration (see Architecture section for storage details)
export MLFLOW_S3_ENDPOINT_URL="http://localhost:9000"
export AWS_ACCESS_KEY_ID="minio"
export AWS_SECRET_ACCESS_KEY="miniopass123"

python kagent_mlflow_logger.py "Your question here"
```

**Note:** If MinIO is running in Kubernetes, set up port forwarding:

```bash
kubectl port-forward svc/mlflow-minio 9000:9000
```

### Programmatic Usage

You can also use the `KagentMLflowLogger` class in your own scripts:

```python
from kagent_mlflow_logger import KagentMLflowLogger

logger = KagentMLflowLogger(
    mlflow_tracking_uri="http://localhost:5000",
    a2a_url="http://localhost:8083/api/a2a/kagent/rh-analyze-simple/",
    experiment_name="rh-analyze-mvp",
    s3_endpoint_url="http://localhost:9000",  # MinIO endpoint
    aws_access_key_id="minio",
    aws_secret_access_key="miniopass123"
)

result = logger.send_question("What is OpenShift?")
print(f"Answer: {result['answer']}")
print(f"Run ID: {result['run_id']}")
```

## What Gets Logged

For each question sent to Kagent, the following is logged to MLflow:

- **Tags:**
  - `agent`: Agent name (rh-analyze-simple)
  - `a2a_url`: A2A endpoint URL
  - `kagent_task_id`: Task ID from Kagent (if available)
  - `kagent_context_id`: Context ID from Kagent (if available)

- **Metrics:**
  - `latency_ms`: Request latency in milliseconds
  - Any metrics from `kagent_usage_metadata` (e.g., token counts)

- **Artifacts:**
  - `question.txt`: The question asked
  - `answer.txt`: The extracted answer
  - `a2a_response.json`: Full JSON response from Kagent

## Viewing Results

View logged runs in the MLflow UI at `http://localhost:5000` in your browser.

If the MLflow UI isn't accessible, you can also start it locally:

```bash
mlflow ui --backend-store-uri http://localhost:5000
```

