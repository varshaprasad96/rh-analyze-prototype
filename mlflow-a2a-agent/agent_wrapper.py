"""
Llama Stack Agent Wrapper for MLflow ResponsesAgent

Uses the official llama-stack-client SDK to interact with Llama Stack,
wrapped in MLflow's ResponsesAgent for automatic tracing.
"""
import os
import logging
from typing import Generator, List, Dict, Any, Optional
from uuid import uuid4

import httpx

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)
from mlflow.models import set_model

from mcp_tools import create_mcp_client_tools

logger = logging.getLogger(__name__)


class LlamaStackAgentWrapper(ResponsesAgent):
    """
    Wraps Llama Stack API calls in MLflow's ResponsesAgent interface.
    
    Features:
    - Direct calls to Llama Stack Agents API
    - Supports RAG via builtin::rag toolgroup
    - Supports dynamic MCP tools via MCP_SERVERS_JSON
    - MLflow auto-tracing enabled
    """
    
    def __init__(self):
        """Initialize the agent from environment variables."""
        super().__init__()
        
        # Load configuration from environment
        self.llamastack_url = os.getenv("LLAMASTACK_URL", "http://localhost:8321")
        self.model = os.getenv("LLAMASTACK_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
        self.instructions = os.getenv("SYSTEM_PROMPT", "You are a helpful AI assistant.")
        
        # Lazy initialization - avoid creating client in __init__ for serialization
        self._client = None
        
        logger.info(f"LlamaStackAgentWrapper initialized")
        logger.info(f"  URL: {self.llamastack_url}")
        logger.info(f"  Model: {self.model}")
    
    @property
    def client(self) -> httpx.Client:
        """Lazy-load the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(base_url=self.llamastack_url, timeout=60.0)
            logger.info(f"Created HTTP client for {self.llamastack_url}")
        return self._client
    
    def _convert_messages(self, request: ResponsesAgentRequest) -> List[Dict[str, Any]]:
        """Convert ResponsesAgentRequest input to Llama Stack message format."""
        messages = []
        
        for item in request.input:
            if hasattr(item, "role") and hasattr(item, "content"):
                content = item.content
                if isinstance(content, str):
                    messages.append({"role": item.role, "content": content})
                elif isinstance(content, list):
                    # Handle multi-part content
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text" or "text" in part:
                                text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    messages.append({
                        "role": item.role,
                        "content": "\n".join(text_parts) if text_parts else "",
                    })
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
                if isinstance(content, list):
                    text_parts = [str(part.get("text", part)) for part in content if isinstance(part, (dict, str))]
                    content = "\n".join(text_parts) if text_parts else ""
                messages.append({"role": role, "content": str(content)})
        
        return messages
    
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """
        Process a request using the Llama Stack agent.
        
        Uses non-streaming mode for simplicity.
        """
        # Collect outputs from streaming
        outputs = []
        for event in self.predict_stream(request):
            if event.type == "response.output_item.done":
                outputs.append(event.item)
        
        return ResponsesAgentResponse(
            output=outputs,
            custom_outputs=request.custom_inputs if hasattr(request, "custom_inputs") else {},
        )
    
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Process a request and stream responses from Llama Stack.
        
        Uses the chat completions API endpoint (OpenAI-compatible).
        """
        messages = self._convert_messages(request)
        
        logger.info(f"Creating chat completion with {len(messages)} messages")
        
        item_id = f"msg_{uuid4().hex[:8]}"
        accumulated_text = ""
        
        try:
            # Use chat completions API (OpenAI-compatible)
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response from choices
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")
                if content:
                    accumulated_text = content
            
            # Emit final output
            if accumulated_text:
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_text_output_item(
                        text=accumulated_text,
                        id=item_id,
                    ),
                )
            else:
                # Empty response
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_text_output_item(
                        text="(No response from LLM)",
                        id=item_id,
                    ),
                )
                
        except Exception as e:
            logger.error(f"Error during chat completion: {e}", exc_info=True)
            # Emit error as text output
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=self.create_text_output_item(
                    text=f"Error: {str(e)}",
                    id=item_id,
                ),
            )


# Create and register the agent instance
def create_agent() -> LlamaStackAgentWrapper:
    """Factory function to create the agent."""
    return LlamaStackAgentWrapper()


# For MLflow model serving - instantiate and register
agent = create_agent()
set_model(agent)

