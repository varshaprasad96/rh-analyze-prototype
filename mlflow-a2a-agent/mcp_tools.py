"""
Dynamic MCP Tool Registration

Creates ClientTool wrappers for MCP servers defined in MCP_SERVERS_JSON.
Supports environment variable substitution in headers for secure token injection.
"""
import os
import json
import re
import logging
from typing import Any, Dict, List, Optional
from functools import partial

import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    def replace(match):
        var_name = match.group(1)
        return os.getenv(var_name, "")
    return re.sub(r'\$\{(\w+)\}', replace, value)


def load_mcp_config() -> List[Dict[str, Any]]:
    """Load MCP server configuration with environment variable substitution."""
    config_str = os.getenv("MCP_SERVERS_JSON", "[]")
    
    # Substitute environment variables in the entire JSON string
    config_str = substitute_env_vars(config_str)
    
    try:
        config = json.loads(config_str)
        logger.info(f"Loaded {len(config)} MCP server configurations")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse MCP_SERVERS_JSON: {e}")
        return []


def discover_mcp_tools(server_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Discover available tools from an MCP server.
    
    Calls the tools/list method to get tool definitions.
    """
    url = server_config["url"]
    headers = server_config.get("headers", {})
    
    # Substitute env vars in headers
    headers = {k: substitute_env_vars(v) for k, v in headers.items()}
    
    try:
        # MCP tools/list request
        response = httpx.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            },
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            logger.info(f"Discovered {len(tools)} tools from {server_config['name']}")
            return tools
        else:
            logger.warning(f"No tools found in response from {server_config['name']}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to discover tools from {server_config['name']}: {e}")
        return []


def call_mcp_tool(
    server_config: Dict[str, Any],
    tool_name: str,
    arguments: Dict[str, Any]
) -> Any:
    """
    Call an MCP tool and return the result.
    """
    url = server_config["url"]
    headers = server_config.get("headers", {})
    
    # Substitute env vars in headers
    headers = {k: substitute_env_vars(v) for k, v in headers.items()}
    
    try:
        response = httpx.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": 1
            },
            headers=headers,
            timeout=60.0
        )
        response.raise_for_status()
        result = response.json()
        
        if "result" in result:
            content = result["result"].get("content", [])
            # Extract text content from MCP response
            if isinstance(content, list):
                texts = [c.get("text", str(c)) for c in content if isinstance(c, dict)]
                return "\n".join(texts) if texts else str(content)
            return str(content)
        elif "error" in result:
            return f"Error: {result['error'].get('message', 'Unknown error')}"
        else:
            return str(result)
            
    except Exception as e:
        logger.error(f"Failed to call MCP tool {tool_name}: {e}")
        return f"Error calling tool: {e}"


def create_mcp_tool_dict(server_config: Dict[str, Any], tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a tool definition dictionary for Llama Stack.
    
    Returns a tool in the format expected by Llama Stack agents API.
    """
    tool_name = f"{server_config['name']}_{tool_def.get('name', '')}"
    
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_def.get("description", "MCP tool"),
            "parameters": tool_def.get("inputSchema", {})
        }
    }


def create_mcp_client_tools() -> List[Dict[str, Any]]:
    """
    Create tool definitions for each MCP server/tool combination.
    
    Returns a list of tool dictionaries for Llama Stack.
    """
    tools: List[Dict[str, Any]] = []
    
    for server_config in load_mcp_config():
        server_name = server_config.get("name", "unknown")
        tool_whitelist = server_config.get("tools", [])
        
        logger.info(f"Processing MCP server: {server_name}")
        
        # Discover available tools
        mcp_tools = discover_mcp_tools(server_config)
        
        for tool_def in mcp_tools:
            tool_name = tool_def.get("name", "")
            
            # Filter by whitelist if specified
            if tool_whitelist and tool_name not in tool_whitelist:
                logger.debug(f"Skipping tool {tool_name} (not in whitelist)")
                continue
            
            # Create tool dictionary
            tool_dict = create_mcp_tool_dict(server_config, tool_def)
            tools.append(tool_dict)
            logger.info(f"Registered tool: {tool_dict['function']['name']}")
    
    logger.info(f"Total MCP tools registered: {len(tools)}")
    return tools


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with sample config
    os.environ["MCP_SERVERS_JSON"] = json.dumps([
        {
            "name": "test",
            "url": "http://localhost:8080/mcp",
            "tools": ["test_tool"]
        }
    ])
    
    tools = create_mcp_client_tools()
    print(f"Created {len(tools)} tools")

