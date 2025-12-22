#!/usr/bin/env python3
"""
Llamastack Agent Wrapper for MLflow ResponsesAgent (Direct Instantiation)

This module wraps a Llamastack agent directly, similar to how LangGraph agents
are wrapped. The agent is instantiated and passed to set_model(), not logged
from a file.
"""

from typing import Generator, Optional
import requests

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)
from mlflow.models import set_model
from openai import OpenAI


class LlamastackAgentWrapper(ResponsesAgent):
    """
    Wraps a Llamastack agent in a ResponsesAgent interface.
    
    Similar to LangGraph wrapper pattern - the agent is instantiated directly
    and wrapped, rather than loaded from a file.
    
    Usage:
        from llamastack_agent_wrapper_direct import LlamastackAgentWrapper
        from mlflow.models import set_model
        
        agent = LlamastackAgentWrapper(
            llamastack_base_url="http://localhost:8321",
            agent_id="my-agent"
        )
        set_model(agent)
    """
    
    def __init__(
        self,
        llamastack_base_url: str,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list] = None,
    ):
        """
        Initialize the Llamastack Agent Wrapper.
        
        Agent ID Specification:
        - If agent_id is provided (e.g., from LLAMASTACK_AGENT_ID env var), use that existing agent
        - If agent_id is None, create a new agent via POST /v1/agents with the specified tools
        - The API returns an agent_id (UUID) which is stored in self.agent_id
        
        RAG Setup:
        - For RAG to work properly, you need to:
          1. Create a vector DB: POST /v1/vector-dbs with documents
          2. Get the vector_db_id from the response
          3. Register RAG tool with vector_db_ids:
             {"name": "builtin::rag/knowledge_search", "args": {"vector_db_ids": [vector_db_id]}}
        - Currently, we register the RAG tool with empty args (no vector_db_ids)
          This may work if Llamastack has a default vector DB configured, but for proper RAG,
          you should create a vector DB first and pass vector_db_ids in the tool args.
        
        Args:
            llamastack_base_url: Base URL for Llamastack server
            agent_id: ID of an existing agent in Llamastack, or None to create a new one
            api_key: API key for authentication (optional)
            model: Model identifier to use for the agent (defaults to agent_id if provided)
            tools: List of tools to register with the agent (e.g., [{"name": "builtin::rag/knowledge_search", "args": {}}])
        """
        super().__init__()
        
        self.llamastack_base_url = llamastack_base_url
        if self.llamastack_base_url.endswith("/v1"):
            self.llamastack_base_url = self.llamastack_base_url[:-3]
        
        self.api_key = api_key or "fake"
        self.model = model or agent_id or "ollama/llama3.2:1b"
        self.tools = tools or []
        
        # Don't initialize OpenAI client here - lazy load it to avoid serialization issues
        # The client will be created when needed in predict/predict_stream
        self._client = None
        
        # If agent_id is provided, use existing agent; otherwise create/register one
        if agent_id:
            self.agent_id = agent_id
        else:
            # Create a new agent with tools registered
            self.agent_id = self._create_agent_with_tools()
    
    def _convert_messages(self, request: ResponsesAgentRequest) -> list:
        """Convert ResponsesAgentRequest input to chat format."""
        messages = []
        for item in request.input:
            if hasattr(item, "role") and hasattr(item, "content"):
                content = item.content
                if isinstance(content, str):
                    messages.append({"role": item.role, "content": content})
                elif isinstance(content, list):
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
    
    def _convert_tools(self, request: ResponsesAgentRequest) -> Optional[list]:
        """Convert tools from request to OpenAI format."""
        if not hasattr(request, "tools") or not request.tools:
            return None
        
        tools = []
        for tool in request.tools:
            if isinstance(tool, dict):
                tools.append(tool)
            elif hasattr(tool, "model_dump"):
                tools.append(tool.model_dump())
        
        return tools if tools else None
    
    @property
    def client(self):
        """Lazy-load OpenAI client to avoid serialization issues."""
        if self._client is None:
            self._client = OpenAI(
                base_url=f"{self.llamastack_base_url}/v1",
                api_key=self.api_key,
            )
        return self._client
    
    def _create_agent_with_tools(self) -> str:
        """
        Create and register an agent in Llamastack with tools.
        
        Returns:
            The agent_id of the created agent
        """
        import requests
        import uuid
        
        # Generate a unique agent ID
        agent_id = f"mlflow-agent-{uuid.uuid4().hex[:8]}"
        
        # Prepare agent creation payload
        # Following the tutorial pattern: create agent with model and tools
        # The API expects agent_config with agent_id, model, instructions, and tools
        agent_payload = {
            "agent_id": agent_id,
            "agent_config": {
                "model": self.model,
                "instructions": "You are a helpful assistant. Use available tools to answer questions accurately.",
                "tools": self.tools if self.tools else [
                    # Default: register RAG tool if available
                    {
                        "name": "builtin::rag/knowledge_search",
                        "args": {}
                    }
                ]
            }
        }
        
        try:
            # Create agent via Llamastack Agents API
            # POST /v1/agents with agent_config in the payload
            # Build headers - only include Authorization if api_key is not "fake"
            headers = {}
            if self.api_key != "fake":
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.llamastack_base_url}/v1/agents",
                json=agent_payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                # The API may return a different agent_id (UUID)
                result = response.json()
                created_agent_id = result.get("agent_id", agent_id)
                print(f"✓ Created agent '{created_agent_id}' with tools in Llamastack")
                return created_agent_id
            else:
                print(f"⚠️  Could not create agent via API (status {response.status_code}), using model directly")
                print(f"   Response: {response.text[:200]}")
                # Fallback: use model identifier as agent_id
                return self.model
        except Exception as e:
            print(f"⚠️  Could not create agent in Llamastack: {e}")
            print(f"   Falling back to using model '{self.model}' directly")
            # Fallback: use model identifier as agent_id
            return self.model
    
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """
        Process a request using Llamastack agent.
        
        Agent ID Specification:
        - If LLAMASTACK_AGENT_ID env var is set, use that existing agent
        - Otherwise, create a new agent with tools via POST /v1/agents
        - The API returns an agent_id (UUID) which we store in self.agent_id
        
        RAG Setup:
        - For RAG to work, you need to:
          1. Create a vector DB: POST /v1/vector-dbs with documents
          2. Get the vector_db_id from the response
          3. Register RAG tool with vector_db_ids: {"name": "builtin::rag/knowledge_search", "args": {"vector_db_ids": [vector_db_id]}}
        - Currently, we register the RAG tool without vector_db_ids (empty args)
          which may work if Llamastack has a default vector DB configured
        
        Similar to LangGraph pattern - wraps the agent's execution.
        """
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        
        return ResponsesAgentResponse(
            output=outputs,
            custom_outputs=request.custom_inputs if hasattr(request, "custom_inputs") else {},
        )
    
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Process a request and stream responses from Llamastack agent.
        
        Uses the Agents API to create turns, which allows the agent to use tools (e.g., RAG).
        The agent_id is specified during initialization:
        - If LLAMASTACK_AGENT_ID env var is set, use that existing agent
        - Otherwise, a new agent is created with tools via _create_agent_with_tools()
        
        For RAG to work, the agent must be created with a RAG tool that has vector_db_ids configured.
        
        Similar to LangGraph's stream pattern - yields events as they come.
        """
        # Convert request to chat format
        messages = self._convert_messages(request)
        tools = self._convert_tools(request)
        
        # Use Llamastack Agents API to create a turn
        # This allows the agent to use its registered tools (e.g., RAG)
        import requests
        import uuid
        
        # Create a session for this conversation
        session_id = str(uuid.uuid4())
        
        # Create a turn with the user message
        # The agent will process the turn and use tools if needed
        turn_payload = {
            "messages": messages,
            "stream": True,  # Request streaming response
        }
        
        try:
            # Use Agents API for turn creation (enables tool calling)
            # Build headers - only include Authorization if api_key is not "fake"
            headers = {
                "Accept": "text/event-stream" if turn_payload.get("stream") else "application/json",
            }
            if self.api_key != "fake":
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.llamastack_base_url}/v1/agents/{self.agent_id}/session/{session_id}/turn",
                json=turn_payload,
                headers=headers,
                stream=True,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                # Fallback to chat completions API if Agents API fails
                print(f"⚠️  Agents API returned {response.status_code}, falling back to chat completions")
                yield from self._predict_stream_via_chat_completions(messages, tools)
                return
            
            # Parse streaming response from Agents API
            # The format may be SSE (Server-Sent Events) or JSON streaming
            item_id = None
            accumulated_text = ""
            tool_calls = {}
            
            for line in response.iter_lines():
                if not line:
                    continue
                
                # Try to parse as JSON (non-SSE format)
                try:
                    import json
                    data = json.loads(line)
                    
                    # Handle different response formats
                    if "content" in data:
                        if item_id is None:
                            item_id = f"msg_{uuid.uuid4().hex[:8]}"
                        accumulated_text += data["content"]
                        yield ResponsesAgentStreamEvent(
                            **self.create_text_delta(
                                delta=data["content"],
                                item_id=item_id,
                            )
                        )
                    
                    if "tool_calls" in data or "function_calls" in data:
                        tool_calls_data = data.get("tool_calls") or data.get("function_calls", [])
                        for tool_call_data in tool_calls_data:
                            yield ResponsesAgentStreamEvent(
                                **self.create_function_call_delta(
                                    id=tool_call_data.get("id", f"fc_{uuid.uuid4().hex[:8]}"),
                                    call_id=tool_call_data.get("call_id", tool_call_data.get("id")),
                                    name=tool_call_data.get("name", tool_call_data.get("function", {}).get("name", "")),
                                    arguments=tool_call_data.get("arguments", tool_call_data.get("function", {}).get("arguments", "{}")),
                                ),
                            )
                    
                    # If response is complete
                    if data.get("done") or data.get("finished"):
                        if accumulated_text:
                            yield ResponsesAgentStreamEvent(
                                type="response.output_item.done",
                                item=self.create_text_output_item(
                                    text=accumulated_text,
                                    id=item_id,
                                ),
                            )
                        return
                        
                except json.JSONDecodeError:
                    # Might be SSE format: "data: {...}"
                    if line.startswith(b"data: "):
                        try:
                            data = json.loads(line[6:])  # Skip "data: " prefix
                            # Process same as above
                            continue
                        except:
                            pass
                    continue
            
            # Finalize any accumulated text
            if accumulated_text and item_id:
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_text_output_item(
                        text=accumulated_text,
                        id=item_id,
                    ),
                )
            
        except Exception as e:
            print(f"⚠️  Error using Agents API: {e}")
            # Fallback to chat completions
            yield from self._predict_stream_via_chat_completions(messages, tools)
    
    def _predict_stream_via_chat_completions(
        self, messages: list, tools: Optional[list]
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Fallback method: Use chat completions API directly for streaming.
        """
        # Prepare chat completion parameters
        chat_params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        
        if tools:
            chat_params["tools"] = tools
        
        # Stream from Llamastack via OpenAI client
        stream = self.client.chat.completions.create(**chat_params)
        
        item_id = None
        accumulated_text = ""
        tool_calls = {}
        
        for chunk in stream:
            if not chunk.choices:
                continue
            
            choice = chunk.choices[0]
            delta = choice.delta
            
            # Handle streaming text content
            if delta.content:
                if item_id is None:
                    import uuid
                    item_id = f"msg_{uuid.uuid4().hex[:8]}"
                
                accumulated_text += delta.content
                yield ResponsesAgentStreamEvent(
                    **self.create_text_delta(
                        delta=delta.content,
                        item_id=item_id,
                    )
                )
            
            # Handle streaming tool calls
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    call_id = tool_call_delta.id
                    if call_id not in tool_calls:
                        tool_calls[call_id] = {
                            "id": f"fc_{call_id}",
                            "call_id": call_id,
                            "name": "",
                            "arguments": "",
                        }
                    
                    if tool_call_delta.function.name:
                        tool_calls[call_id]["name"] = tool_call_delta.function.name
                    if tool_call_delta.function.arguments:
                        tool_calls[call_id]["arguments"] += tool_call_delta.function.arguments
        
        # Emit final text output item
        if item_id and accumulated_text:
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=self.create_text_output_item(
                    text=accumulated_text,
                    id=item_id,
                ),
            )
        
        # Emit tool call items
        for call_id, tool_call_data in tool_calls.items():
            if tool_call_data["name"]:
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done",
                    item=self.create_function_call_item(
                        id=tool_call_data["id"],
                        call_id=tool_call_data["call_id"],
                        name=tool_call_data["name"],
                        arguments=tool_call_data["arguments"],
                    ),
                )


# Instantiate the agent and set it for MLflow (similar to LangGraph pattern)
# This allows MLflow to find the model when logging from a file
import os

llamastack_base_url = os.getenv("LLAMASTACK_BASE_URL", "http://localhost:8321")
agent_id = os.getenv("LLAMASTACK_AGENT_ID")  # None = create new agent with tools
model = os.getenv("LLAMASTACK_MODEL", "ollama/llama3.2:1b")
api_key = os.getenv("LLAMASTACK_API_KEY", "fake")

# Define tools to register with the agent
# Following the tutorial pattern: register RAG tool
tools = [
    {
        "name": "builtin::rag/knowledge_search",
        "args": {}
    }
]

# Create the agent instance (like LangGraph does)
# If agent_id is None, it will create a new agent with tools registered
agent = LlamastackAgentWrapper(
    llamastack_base_url=llamastack_base_url,
    agent_id=agent_id,  # None = create new agent
    api_key=api_key,
    model=model,
    tools=tools,  # Register tools with the agent
)

# Set the model for MLflow (like LangGraph does)
set_model(agent)

