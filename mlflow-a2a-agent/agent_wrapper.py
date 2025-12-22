"""
Llama Stack Agent Wrapper for MLflow ResponsesAgent

Uses the official llama-stack-client SDK to interact with Llama Stack,
wrapped in MLflow's ResponsesAgent for automatic tracing.
"""
import os
import logging
from typing import Generator, List, Dict, Any, Optional, Union
from uuid import uuid4

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.types.shared_params.agent_config import Toolgroup

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
    Wraps a Llama Stack agent using the official SDK in MLflow's ResponsesAgent interface.
    
    Features:
    - Uses llama-stack-client's Agent class for session/turn management
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
        self._agent = None
        self._session_id = None
        
        logger.info(f"LlamaStackAgentWrapper initialized")
        logger.info(f"  URL: {self.llamastack_url}")
        logger.info(f"  Model: {self.model}")
    
    @property
    def client(self) -> LlamaStackClient:
        """Lazy-load the Llama Stack client."""
        if self._client is None:
            self._client = LlamaStackClient(base_url=self.llamastack_url)
            logger.info(f"Created LlamaStackClient for {self.llamastack_url}")
        return self._client
    
    @property
    def agent(self) -> Agent:
        """Lazy-load the Agent instance."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent
    
    def _build_tools(self) -> List[Union[Toolgroup, Any]]:
        """Build the tools list from environment configuration."""
        tools = []
        
        # Add RAG toolgroup if enabled
        rag_enabled = os.getenv("RAG_ENABLED", "false").lower() == "true"
        if rag_enabled:
            vector_store_ids = os.getenv("VECTOR_STORE_IDS", "")
            vector_db_ids = [v.strip() for v in vector_store_ids.split(",") if v.strip()]
            
            if vector_db_ids:
                tools.append(Toolgroup(
                    name="builtin::rag",
                    args={"vector_db_ids": vector_db_ids}
                ))
                logger.info(f"Added RAG toolgroup with vector DBs: {vector_db_ids}")
            else:
                logger.warning("RAG_ENABLED=true but no VECTOR_STORE_IDS provided")
        
        # Add MCP client tools
        try:
            mcp_tools = create_mcp_client_tools()
            tools.extend(mcp_tools)
            logger.info(f"Added {len(mcp_tools)} MCP tools")
        except Exception as e:
            logger.error(f"Failed to create MCP tools: {e}")
        
        return tools
    
    def _create_agent(self) -> Agent:
        """Create the Llama Stack Agent instance."""
        tools = self._build_tools()
        
        agent = Agent(
            client=self.client,
            model=self.model,
            instructions=self.instructions,
            tools=tools if tools else None,
        )
        
        logger.info(f"Created Agent with {len(tools)} tools")
        return agent
    
    def _get_or_create_session(self) -> str:
        """Get existing session or create a new one."""
        if self._session_id is None:
            session_name = f"a2a-session-{uuid4().hex[:8]}"
            self._session_id = self.agent.create_session(session_name)
            logger.info(f"Created new session: {self._session_id}")
        return self._session_id
    
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
        Process a request and stream responses from the Llama Stack agent.
        
        Uses the Agent's create_turn method with streaming.
        """
        messages = self._convert_messages(request)
        session_id = self._get_or_create_session()
        
        logger.info(f"Creating turn with {len(messages)} messages")
        
        item_id = f"msg_{uuid4().hex[:8]}"
        accumulated_text = ""
        
        try:
            # Use streaming turn
            for chunk in self.agent.create_turn(messages, session_id, stream=True):
                event = chunk.event
                
                # Handle different event types from the SDK
                if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                    delta_text = event.delta.text
                    if delta_text:
                        accumulated_text += delta_text
                        yield ResponsesAgentStreamEvent(
                            **self.create_text_delta(
                                delta=delta_text,
                                item_id=item_id,
                            )
                        )
                
                # Check if turn is complete
                if chunk.response is not None:
                    # Turn completed - emit final output item
                    if accumulated_text:
                        yield ResponsesAgentStreamEvent(
                            type="response.output_item.done",
                            item=self.create_text_output_item(
                                text=accumulated_text,
                                id=item_id,
                            ),
                        )
                    break
            
            # If we didn't emit anything, emit the accumulated text
            if accumulated_text and not any(True for _ in []):
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_text_output_item(
                        text=accumulated_text,
                        id=item_id,
                    ),
                )
                
        except Exception as e:
            logger.error(f"Error during turn: {e}")
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

