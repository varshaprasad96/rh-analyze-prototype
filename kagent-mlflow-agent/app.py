import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
import mlflow
from fastapi import FastAPI, HTTPException, Request


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError as e:
        raise RuntimeError(f"Invalid int for {name}: {val}") from e


LLAMASTACK_URL = os.getenv("LLAMASTACK_URL", "http://llama-stack-service:8321").rstrip("/")
LLAMASTACK_MODEL = os.getenv("LLAMASTACK_MODEL", "vllm-inference-1/qwen3-14b-awq")

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()
SEARCH_MODE = os.getenv("SEARCH_MODE", "hybrid").strip()  # vector|keyword|hybrid
MAX_RESULTS = _env_int("MAX_RESULTS", 5)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "").strip()
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "kagent-mlflow-agent").strip()


def _extract_last_user_text(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            # OpenAI can send rich content arrays; keep it minimal
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                return "\n".join([p for p in parts if p]).strip()
    return ""


def _format_vector_results(store_id: str, results: Dict[str, Any]) -> Tuple[str, int]:
    data = results.get("data", []) if isinstance(results, dict) else []
    if not data:
        return "No relevant documentation found.", 0

    chunks: List[str] = []
    for i, item in enumerate(data[:MAX_RESULTS], 1):
        filename = item.get("filename", "unknown")
        score = item.get("score", 0)
        content = ""
        if item.get("content") and isinstance(item["content"], list) and item["content"]:
            first = item["content"][0]
            if isinstance(first, dict):
                content = first.get("text", "")
        if len(content) > 1200:
            content = content[:1200] + "..."
        chunks.append(f"[{i}] {filename} (score={score:.3f}, store=...{store_id[-12:]})\n{content}")
    return "\n\n".join(chunks), len(chunks)


async def _search_vector_store(client: httpx.AsyncClient, query: str) -> Tuple[str, int, float]:
    if not VECTOR_STORE_ID:
        return "VECTOR_STORE_ID is not configured; retrieval is disabled.", 0, 0.0
    if not query:
        return "Empty query; retrieval skipped.", 0, 0.0

    payload = {
        "query": query,
        "max_num_results": MAX_RESULTS,
        "search_mode": SEARCH_MODE,
        "rewrite_query": True,
    }

    t0 = time.time()
    resp = await client.post(f"/v1/vector_stores/{VECTOR_STORE_ID}/search", json=payload)
    resp.raise_for_status()
    dt = time.time() - t0
    formatted, count = _format_vector_results(VECTOR_STORE_ID, resp.json())
    return formatted, count, dt


async def _chat_completion(
    client: httpx.AsyncClient,
    messages: List[Dict[str, Any]],
    temperature: Optional[float],
    max_tokens: Optional[int],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"model": LLAMASTACK_MODEL, "messages": messages}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    # Pass through tools for function calling (MCP tools from kagent)
    if tools:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    resp = await client.post("/v1/chat/completions", json=payload)
    resp.raise_for_status()
    return resp.json()


def _init_mlflow() -> None:
    if not MLFLOW_TRACKING_URI:
        return
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)


app = FastAPI(title="kagent-mlflow-agent adapter", version="0.1.0")


# Store last request info for debugging
_last_request_info: Dict[str, Any] = {}

@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {
        "ok": True,
        "llamastack_url": LLAMASTACK_URL,
        "llamastack_model": LLAMASTACK_MODEL,
        "vector_store_id_set": bool(VECTOR_STORE_ID),
        "mlflow_tracking_uri_set": bool(MLFLOW_TRACKING_URI),
    }

@app.get("/debug/last-request")
def debug_last_request() -> Dict[str, Any]:
    """Debug endpoint to see what kagent sent in the last request."""
    return _last_request_info


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Dict[str, Any]:
    """
    Minimal OpenAI Chat Completions compatible endpoint for kagent ModelConfig provider=OpenAI.

    - Performs retrieval via Llama Stack vector store search
    - Injects retrieval context into the prompt
    - Calls Llama Stack chat completions (vLLM-backed)
    - Logs everything to MLflow (server-side) when configured
    """
    global _last_request_info
    body = await request.json()
    
    # Store debug info
    _last_request_info = {
        "keys": list(body.keys()),
        "has_tools": bool(body.get("tools")),
        "tools_count": len(body.get("tools", [])) if body.get("tools") else 0,
        "tool_names": [t.get("function", {}).get("name") for t in body.get("tools", [])[:5]] if body.get("tools") else [],
        "model": body.get("model"),
        "message_count": len(body.get("messages", [])),
    }
    
    messages = body.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="Missing/invalid 'messages'")

    # kagent generally expects non-stream responses; be explicit.
    if body.get("stream") is True:
        raise HTTPException(status_code=400, detail="Streaming is not supported by this adapter. Set stream=false.")

    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")
    # Pass through tools for MCP function calling
    tools = body.get("tools")
    tool_choice = body.get("tool_choice")
    query_text = _extract_last_user_text(messages)

    _init_mlflow()
    req_id = str(uuid.uuid4())

    run = None
    if MLFLOW_TRACKING_URI:
        run = mlflow.start_run(run_name=f"kagent-chat-{req_id[:8]}")
        mlflow.set_tag("component", "kagent-mlflow-agent-adapter")
        mlflow.set_tag("request_id", req_id)
        mlflow.set_tag("llamastack_model", LLAMASTACK_MODEL)
        mlflow.set_tag("search_mode", SEARCH_MODE)
        if VECTOR_STORE_ID:
            mlflow.set_tag("vector_store_id", VECTOR_STORE_ID)
        mlflow.log_param("max_results", MAX_RESULTS)

    try:
        async with httpx.AsyncClient(base_url=LLAMASTACK_URL, timeout=60.0) as client:
            retrieval_context, retrieved_n, retrieval_s = await _search_vector_store(client, query_text)

            # Inject retrieval as a system message (prepend).
            rag_system = {
                "role": "system",
                "content": (
                    "You are an assistant with access to a retrieved context section.\n"
                    "Use the context when it is relevant. If the context is not relevant, answer normally.\n\n"
                    "Retrieved context:\n"
                    f"{retrieval_context}"
                ),
            }
            augmented_messages = [rag_system] + messages

            t0 = time.time()
            completion = await _chat_completion(
                client,
                augmented_messages,
                temperature=temperature if isinstance(temperature, (int, float)) else None,
                max_tokens=max_tokens if isinstance(max_tokens, int) else None,
                tools=tools,
                tool_choice=tool_choice,
            )
            model_s = time.time() - t0

        if run:
            mlflow.log_metric("retrieval_seconds", retrieval_s)
            mlflow.log_metric("retrieval_results", retrieved_n)
            mlflow.log_metric("model_seconds", model_s)
            mlflow.log_text(query_text[:4000], "prompt_last_user.txt")
            mlflow.log_text(retrieval_context[:20000], "retrieval_context.txt")

            # Log tool usage if present
            if tools:
                tool_names = [t.get("function", {}).get("name", "unknown") for t in tools if isinstance(t, dict)]
                mlflow.set_tag("tools_available", ",".join(tool_names[:20]))

            # Best-effort response text extraction
            resp_text = ""
            tool_calls = None
            try:
                msg = completion["choices"][0]["message"]
                resp_text = msg.get("content") or ""
                tool_calls = msg.get("tool_calls")
            except Exception:
                resp_text = str(completion)[:4000]
            
            if resp_text:
                mlflow.log_text(resp_text[:20000], "response.txt")
            if tool_calls:
                mlflow.log_text(json.dumps(tool_calls, indent=2)[:20000], "tool_calls.json")
                mlflow.set_tag("tool_call_count", len(tool_calls))

        return completion

    except httpx.HTTPStatusError as e:
        if run:
            mlflow.set_tag("error", "http_status")
            mlflow.set_tag("error_detail", str(e))
        raise HTTPException(status_code=502, detail=f"Llama Stack error: {e}") from e
    except Exception as e:
        if run:
            mlflow.set_tag("error", "exception")
            mlflow.set_tag("error_detail", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if run:
            mlflow.end_run()


