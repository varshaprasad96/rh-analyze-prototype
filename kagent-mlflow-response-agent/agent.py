"""
MLflow ResponsesAgent using OpenAI client pointing to Llama Stack.

Features:
- Official OpenAI Python client for clean API interactions
- Native RAG via file_search tool (supports multiple vector stores)
- Native MCP tools (dynamic list from config)
- previous_response_id for conversation continuity
- MLflow ResponsesAgent for automatic tracing

Configuration (via environment variables):
- LLAMASTACK_URL: Llama Stack base URL
- LLAMASTACK_MODEL: Model ID
- VECTOR_STORE_IDS: Comma-separated or JSON array of vector store IDs
- MAX_RESULTS: Max results per vector store search (default: 10)
- MCP_TOOLS: JSON array of MCP server configs, each with:
    - server_url: MCP server URL
    - server_label: Display label
    - headers: (recommended) Headers dict including "Authorization": "Bearer <token>"
    - authorization: (optional, newer Llama Stack only) OAuth token
    - allowed_tools: (optional) List of allowed tool names
"""
import os
import json
import logging
from typing import Generator, List, Dict, Any, Optional

from openai import OpenAI
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)
from mlflow.models import set_model

logger = logging.getLogger(__name__)


def parse_list_env(env_var: str, fallback_env: str = None, default: List[str] = None) -> List[str]:
    """Parse environment variable as list (JSON array or comma-separated).
    
    Args:
        env_var: Primary environment variable name (plural form)
        fallback_env: Fallback environment variable (singular form for backwards compat)
        default: Default value if not set
    """
    value = os.getenv(env_var, "").strip()
    
    # Try fallback (e.g., VECTOR_STORE_ID -> VECTOR_STORE_IDS)
    if not value and fallback_env:
        value = os.getenv(fallback_env, "").strip()
    
    if not value:
        return default or []
    
    # Try JSON first
    if value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    
    # Fall back to comma-separated
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_mcp_tools_env() -> List[Dict[str, Any]]:
    """
    Parse MCP_TOOLS environment variable.
    
    Expected format (JSON array):
    [
        {
            "server_url": "https://api.githubcopilot.com/mcp/x/repos/readonly",
            "server_label": "GitHub",
            "authorization": "ghp_xxxxx"
        },
        ...
    ]
    """
    value = os.getenv("MCP_TOOLS", "").strip()
    if not value:
        return []
    
    try:
        tools = json.loads(value)
        if not isinstance(tools, list):
            logger.warning(f"MCP_TOOLS must be a JSON array, got: {type(tools)}")
            return []
        
        valid_tools = []
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                logger.warning(f"MCP_TOOLS[{i}] must be an object, got: {type(tool)}")
                continue
            
            if "server_url" not in tool or "server_label" not in tool:
                logger.warning(f"MCP_TOOLS[{i}] missing required fields (server_url, server_label)")
                continue
            
            valid_tools.append(tool)
        
        return valid_tools
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse MCP_TOOLS: {e}")
        return []


class LlamaStackAgent(ResponsesAgent):
    """
    Agent using OpenAI client pointed at Llama Stack's /v1/responses API.
    
    Supports:
    - Multiple vector stores for RAG (file_search)
    - Multiple MCP servers for external tools
    - Conversation continuity via previous_response_id
    """
    
    def __init__(self):
        """Initialize from environment variables."""
        super().__init__()
        
        self.base_url = os.getenv("LLAMASTACK_URL", "http://llama-stack-service:8321").rstrip("/") + "/v1"
        self.model = os.getenv("LLAMASTACK_MODEL", "vllm-inference-1/qwen3-14b-awq")
        self.max_results = int(os.getenv("MAX_RESULTS", "10"))
        
        # Parse vector store IDs (list, with fallback to singular for backwards compat)
        self.vector_store_ids = parse_list_env("VECTOR_STORE_IDS", fallback_env="VECTOR_STORE_ID")
        
        # Parse MCP tools config (list of server configs)
        self.mcp_tools = parse_mcp_tools_env()
        
        # OpenAI client pointed at Llama Stack (token not needed)
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="not-needed",
        )
        
        # Store last response_id for conversation continuity
        self._last_response_id: Optional[str] = None
        
        logger.info(f"LlamaStackAgent initialized")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Vector Stores: {self.vector_store_ids or '(none)'}")
        logger.info(f"  MCP Tools: {len(self.mcp_tools)} configured")
        for mcp in self.mcp_tools:
            logger.info(f"    - {mcp.get('server_label')}: {mcp.get('server_url')}")
    
    def _build_tools(self) -> List[Dict[str, Any]]:
        """Build tools list for the request."""
        tools = []
        
        # Add file_search tool for RAG if vector stores are configured
        if self.vector_store_ids:
            tools.append({
                "type": "file_search",
                "vector_store_ids": self.vector_store_ids,
                "max_num_results": self.max_results,
            })
        
        # Add MCP tools
        for mcp_config in self.mcp_tools:
            mcp_tool: Dict[str, Any] = {
                "type": "mcp",
                "server_url": mcp_config["server_url"],
                "server_label": mcp_config["server_label"],
            }
            
            # Add authorization if present (just the token, Llama Stack adds "Bearer")
            if mcp_config.get("authorization"):
                mcp_tool["authorization"] = mcp_config["authorization"]
            
            # Add custom headers if present (NOT for Authorization)
            if mcp_config.get("headers"):
                mcp_tool["headers"] = mcp_config["headers"]
            
            # Add allowed_tools filter if present
            if mcp_config.get("allowed_tools"):
                mcp_tool["allowed_tools"] = mcp_config["allowed_tools"]
            
            tools.append(mcp_tool)
        
        return tools
    
    def _extract_input(self, request: ResponsesAgentRequest) -> str:
        """Extract input text from request."""
        parts = []
        for item in request.input:
            if hasattr(item, "content"):
                content = item.content
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c.get("text", ""))
                        elif isinstance(c, str):
                            parts.append(c)
            elif isinstance(item, dict):
                content = item.get("content", "")
                if isinstance(content, str):
                    parts.append(content)
        
        return "\n".join(parts) if parts else ""
    
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """Process request (non-streaming)."""
        outputs = []
        for event in self.predict_stream(request):
            if event.type == "response.output_item.done":
                outputs.append(event.item)
        
        return ResponsesAgentResponse(
            output=outputs,
            custom_outputs=getattr(request, "custom_inputs", {}),
        )
    
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """Process request using OpenAI client's responses API."""
        
        input_text = self._extract_input(request)
        tools = self._build_tools()
        
        try:
            logger.info(f"Calling /v1/responses with {len(tools)} tools")
            for t in tools:
                logger.info(f"  Tool: {t.get('type')} - {t.get('server_label', t.get('vector_store_ids', ''))}")
            
            # Build kwargs
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "input": input_text,
            }
            
            if tools:
                kwargs["tools"] = tools
            
            # Add previous_response_id for conversation continuity
            if self._last_response_id:
                kwargs["previous_response_id"] = self._last_response_id
            
            # Use OpenAI client's responses API
            response = self.client.responses.create(**kwargs)
            
            # Store response_id for next turn
            self._last_response_id = response.id
            logger.info(f"Response ID: {response.id}")
            
            # Extract text from output
            accumulated_text = ""
            
            for output_item in response.output:
                item_type = getattr(output_item, "type", "unknown")
                
                if item_type == "file_search_call":
                    results = getattr(output_item, "results", []) or []
                    logger.info(f"RAG file_search returned {len(results)} results")
                
                elif item_type == "mcp_list_tools":
                    tools_list = getattr(output_item, "tools", []) or []
                    logger.info(f"MCP list_tools returned {len(tools_list)} tools")
                
                elif item_type == "mcp_call":
                    tool_name = getattr(output_item, "name", "unknown")
                    error = getattr(output_item, "error", None)
                    if error:
                        logger.warning(f"MCP call {tool_name} error: {error}")
                    else:
                        logger.info(f"MCP call {tool_name} succeeded")
                
                elif item_type == "message":
                    for content in output_item.content:
                        if content.type == "output_text":
                            text = content.text or ""
                            # Remove thinking tags if present
                            if "</think>" in text:
                                text = text.split("</think>")[-1].strip()
                            accumulated_text += text
            
            # Log token usage
            if response.usage:
                logger.info(f"Tokens: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
            
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=self.create_text_output_item(
                    text=accumulated_text or "(No response)",
                    id=f"msg_{response.id[-8:] if response.id else 'unknown'}",
                ),
            )
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Response API error: {error_str}")
            
            # Reset conversation context on server errors
            if "500" in error_str:
                logger.info("Resetting conversation context due to server error")
                self._last_response_id = None
            
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=self.create_text_output_item(
                    text=f"Error: {error_str}",
                    id="msg_error",
                ),
            )
    
    def reset_conversation(self):
        """Reset conversation context (clear previous_response_id)."""
        self._last_response_id = None


# Create and register agent
def create_agent() -> LlamaStackAgent:
    """Factory function."""
    return LlamaStackAgent()


agent = create_agent()
set_model(agent)
