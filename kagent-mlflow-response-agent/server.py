"""
OpenAI-compatible API server for kagent ModelConfig.

This server:
- Provides /v1/chat/completions endpoint (OpenAI format) for kagent
- Uses LlamaStackAgent with native RAG via file_search
- Logs all interactions to MLflow
"""
import os
import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

import mlflow
from mlflow.types.responses import ResponsesAgentRequest

from agent import LlamaStackAgent

logger = logging.getLogger(__name__)

# Global agent
agent: Optional[LlamaStackAgent] = None

# MLflow config
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "").strip()
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "kagent-mlflow-response-agent")


def init_mlflow():
    """Initialize MLflow tracking."""
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        logger.info(f"MLflow: {MLFLOW_TRACKING_URI}, experiment: {MLFLOW_EXPERIMENT}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan - init agent and MLflow."""
    global agent
    init_mlflow()
    logger.info("Initializing LlamaStackAgent...")
    agent = LlamaStackAgent()
    logger.info("Agent ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="kagent-mlflow-response-agent",
    description="MLflow ResponsesAgent with native RAG for kagent",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/healthz")
def healthz():
    """Health check."""
    return {
        "ok": True,
        "agent_ready": agent is not None,
        "mlflow_enabled": bool(MLFLOW_TRACKING_URI),
        "vector_stores": agent.vector_store_ids if agent else [],
        "mcp_tools_count": len(agent.mcp_tools) if agent else 0,
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint.
    
    - Accepts OpenAI format from kagent
    - Uses native RAG via Llama Stack file_search
    - Logs to MLflow
    """
    global agent
    
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not ready")
    
    body = await request.json()
    messages = body.get("messages", [])
    
    if not messages:
        raise HTTPException(status_code=400, detail="Missing messages")
    
    # Start MLflow run
    req_id = str(uuid4())
    run = None
    
    if MLFLOW_TRACKING_URI:
        run = mlflow.start_run(run_name=f"kagent-chat-{req_id[:8]}")
        mlflow.set_tag("component", "kagent-mlflow-response-agent")
        mlflow.set_tag("request_id", req_id)
        mlflow.set_tag("model", agent.model)
        if agent.vector_store_ids:
            mlflow.set_tag("vector_store_ids", ",".join(agent.vector_store_ids))
        if agent.mcp_tools:
            mcp_labels = [t.get("server_label", "?") for t in agent.mcp_tools]
            mlflow.set_tag("mcp_tools", ",".join(mcp_labels))
        
        # Log tools if present
        tools = body.get("tools")
        if tools:
            tool_names = [t.get("function", {}).get("name", "?") for t in tools[:10]]
            mlflow.set_tag("tools", ",".join(tool_names))
    
    try:
        # Build ResponsesAgentRequest
        agent_request = ResponsesAgentRequest(
            input=[{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
        )
        
        # Get response from agent (uses native RAG)
        response = agent.predict(agent_request)
        
        # Extract text from response
        output_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                content = item.content
                if isinstance(content, str):
                    output_text += content
                elif hasattr(content, "text"):
                    output_text += content.text or ""
                elif isinstance(content, list):
                    for c in content:
                        if hasattr(c, "text"):
                            output_text += c.text or ""
                        elif isinstance(c, dict) and "text" in c:
                            output_text += c.get("text", "")
            elif hasattr(item, "text"):
                output_text += item.text or ""
            elif isinstance(item, dict) and "text" in item:
                output_text += item["text"]
        
        # Log to MLflow
        if run:
            mlflow.log_text(output_text[:20000], "response.txt")
            user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            mlflow.log_text(user_msg[:4000], "prompt.txt")
        
        result = {
            "id": f"chatcmpl-{req_id[:12]}",
            "object": "chat.completion",
            "model": agent.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": output_text,
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        if run:
            mlflow.set_tag("error", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if run:
            mlflow.end_run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
