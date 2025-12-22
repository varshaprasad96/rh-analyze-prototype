"""
A2A Protocol Server

FastAPI server exposing A2A (Agent-to-Agent) protocol endpoints:
- GET /.well-known/agent.json - Agent card (discovery)
- POST / - JSON-RPC endpoint for A2A tasks
"""
import os
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from agent_wrapper import LlamaStackAgentWrapper
from mlflow.types.responses import ResponsesAgentRequest

logger = logging.getLogger(__name__)

# Global agent instance
agent: Optional[LlamaStackAgentWrapper] = None


# ============================================================================
# A2A Types
# ============================================================================

class AgentSkill(BaseModel):
    """A2A Agent Skill definition."""
    id: str
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class AgentCapabilities(BaseModel):
    """A2A Agent capabilities."""
    streaming: bool = True
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentCard(BaseModel):
    """A2A Agent Card for discovery."""
    name: str
    description: str
    version: str
    url: str
    capabilities: AgentCapabilities = AgentCapabilities()
    defaultInputModes: List[str] = ["text"]
    defaultOutputModes: List[str] = ["text"]
    skills: List[AgentSkill] = []


class TaskMessage(BaseModel):
    """A2A Task message."""
    role: str
    parts: List[Dict[str, Any]]


class TaskArtifact(BaseModel):
    """A2A Task artifact (output)."""
    name: Optional[str] = None
    description: Optional[str] = None
    parts: List[Dict[str, Any]]


class TaskStatus(BaseModel):
    """A2A Task status."""
    state: str  # submitted, working, input-required, completed, failed, canceled
    message: Optional[str] = None


class Task(BaseModel):
    """A2A Task."""
    id: str
    status: TaskStatus
    artifacts: Optional[List[TaskArtifact]] = None


# ============================================================================
# Configuration from Environment
# ============================================================================

def get_agent_card() -> AgentCard:
    """Build AgentCard from environment variables."""
    name = os.getenv("AGENT_NAME", "MLflow A2A Agent")
    description = os.getenv("AGENT_DESCRIPTION", "An AI agent powered by Llama Stack")
    version = os.getenv("AGENT_VERSION", "1.0.0")
    
    # Build URL from pod/service info or use default
    port = int(os.getenv("PORT", "8080"))
    hostname = os.getenv("HOSTNAME", "localhost")
    service_name = os.getenv("SERVICE_NAME", hostname)
    namespace = os.getenv("NAMESPACE", "default")
    
    # In Kubernetes, use service DNS name
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        url = f"http://{service_name}.{namespace}.svc.cluster.local:{port}"
    else:
        url = f"http://{hostname}:{port}"
    
    # Allow URL override
    url = os.getenv("AGENT_URL", url)
    
    # Parse skills from JSON
    skills_json = os.getenv("SKILLS_JSON", '[{"id":"answer","name":"Answer Questions","description":"Answer user questions"}]')
    try:
        skills_data = json.loads(skills_json)
        skills = [AgentSkill(**s) for s in skills_data]
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse SKILLS_JSON: {e}")
        skills = [AgentSkill(id="answer", name="Answer Questions", description="Answer user questions")]
    
    return AgentCard(
        name=name,
        description=description,
        version=version,
        url=url,
        capabilities=AgentCapabilities(streaming=True),
        skills=skills
    )


# ============================================================================
# Task Storage (in-memory for simplicity)
# ============================================================================

tasks: Dict[str, Task] = {}


def create_task(task_id: Optional[str] = None) -> Task:
    """Create a new task."""
    if task_id is None:
        task_id = f"task_{uuid4().hex[:12]}"
    
    task = Task(
        id=task_id,
        status=TaskStatus(state="submitted")
    )
    tasks[task_id] = task
    return task


def update_task_status(task_id: str, state: str, message: Optional[str] = None):
    """Update task status."""
    if task_id in tasks:
        tasks[task_id].status = TaskStatus(state=state, message=message)


def add_task_artifact(task_id: str, artifact: TaskArtifact):
    """Add artifact to task."""
    if task_id in tasks:
        if tasks[task_id].artifacts is None:
            tasks[task_id].artifacts = []
        tasks[task_id].artifacts.append(artifact)


# ============================================================================
# JSON-RPC Handler
# ============================================================================

async def handle_tasks_send(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tasks/send JSON-RPC method."""
    global agent
    
    if agent is None:
        agent = LlamaStackAgentWrapper()
    
    # Extract message from params
    message = params.get("message", {})
    task_id = params.get("id")
    
    # Create task
    task = create_task(task_id)
    task_id = task.id
    
    update_task_status(task_id, "working")
    
    try:
        # Convert A2A message to ResponsesAgentRequest format
        parts = message.get("parts", [])
        content = ""
        for part in parts:
            if part.get("type") == "text":
                content += part.get("text", "")
        
        # Build request
        request = ResponsesAgentRequest(
            input=[{"role": message.get("role", "user"), "content": content}]
        )
        
        # Process with agent
        response = agent.predict(request)
        
        # Extract text from response
        output_text = ""
        for output_item in response.output:
            if hasattr(output_item, "text"):
                output_text += output_item.text
            elif isinstance(output_item, dict) and "text" in output_item:
                output_text += output_item["text"]
        
        # Create artifact
        artifact = TaskArtifact(
            name="response",
            parts=[{"type": "text", "text": output_text}]
        )
        add_task_artifact(task_id, artifact)
        update_task_status(task_id, "completed")
        
    except Exception as e:
        logger.error(f"Task failed: {e}")
        update_task_status(task_id, "failed", str(e))
    
    return tasks[task_id].model_dump()


async def handle_tasks_get(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tasks/get JSON-RPC method."""
    task_id = params.get("id")
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return tasks[task_id].model_dump()


async def handle_tasks_cancel(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tasks/cancel JSON-RPC method."""
    task_id = params.get("id")
    
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    update_task_status(task_id, "canceled")
    return tasks[task_id].model_dump()


JSON_RPC_METHODS = {
    "tasks/send": handle_tasks_send,
    "tasks/get": handle_tasks_get,
    "tasks/cancel": handle_tasks_cancel,
}


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize agent on startup."""
    global agent
    logger.info("Initializing agent...")
    agent = LlamaStackAgentWrapper()
    logger.info("Agent initialized")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="MLflow A2A Agent",
    description="A2A Protocol compatible agent using Llama Stack and MLflow",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/.well-known/agent.json")
async def get_agent_card_endpoint():
    """Return the A2A Agent Card for discovery."""
    card = get_agent_card()
    return card.model_dump()


@app.post("/")
async def json_rpc_endpoint(request: Request):
    """
    JSON-RPC endpoint for A2A protocol.
    
    Supports methods:
    - tasks/send: Submit a task to the agent
    - tasks/get: Get task status and results
    - tasks/cancel: Cancel a running task
    """
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None
            }
        )
    
    # Validate JSON-RPC request
    jsonrpc = body.get("jsonrpc")
    if jsonrpc != "2.0":
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: missing jsonrpc 2.0"},
                "id": body.get("id")
            }
        )
    
    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")
    
    # Handle method
    handler = JSON_RPC_METHODS.get(method)
    if handler is None:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }
        )
    
    try:
        result = await handler(params)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": e.detail},
                "id": request_id
            }
        )
    except Exception as e:
        logger.exception(f"Error handling {method}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": request_id
            }
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    global agent
    if agent is None:
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting A2A server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

