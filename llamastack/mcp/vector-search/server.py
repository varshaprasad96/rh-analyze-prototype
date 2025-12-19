"""
FastMCP Vector Search Server

Generic MCP server that reads configuration from ConfigMap environment variables.
Exposes Llama Stack vector store search. LLM only provides the search query.
"""
import json
import os
import httpx
from fastmcp import FastMCP

# Load configuration from environment variables (set via ConfigMap)
LLAMASTACK_URL = os.getenv("LLAMASTACK_URL", "http://llama-stack:8321")
VECTOR_STORE_IDS_STR = os.getenv("VECTOR_STORE_IDS", "")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "3"))
SEARCH_MODE = os.getenv("SEARCH_MODE", "vector")
REWRITE_QUERY = os.getenv("REWRITE_QUERY", "true").lower() == "true"
COMBINE_RESULTS = os.getenv("COMBINE_RESULTS", "true").lower() == "true"

# Parse vector store IDs (comma-separated or JSON array)
if VECTOR_STORE_IDS_STR.startswith("["):
    VECTOR_STORE_IDS = json.loads(VECTOR_STORE_IDS_STR)
else:
    VECTOR_STORE_IDS = [id.strip() for id in VECTOR_STORE_IDS_STR.split(",") if id.strip()]

print(f"FastMCP Vector Search Server")
print(f"  Llama Stack: {LLAMASTACK_URL}")
print(f"  Vector Stores: {VECTOR_STORE_IDS}")
print(f"  Max Results: {MAX_RESULTS}")
print(f"  Search Mode: {SEARCH_MODE}")
print(f"  Combine: {COMBINE_RESULTS}")

mcp = FastMCP("Llama Stack Vector Search")


@mcp.tool
async def search_knowledge_base(query: str) -> str:
    """Search the documentation knowledge base.
    
    Args:
        query: Natural language search query
    
    Returns:
        Relevant documentation chunks
    """
    if not VECTOR_STORE_IDS:
        return "Error: No vector store IDs configured."
    
    # Build search request
    payload = {
        "query": query,
        "max_num_results": MAX_RESULTS,
        "search_mode": SEARCH_MODE,
        "rewrite_query": REWRITE_QUERY
    }
    
    try:
        async with httpx.AsyncClient(base_url=LLAMASTACK_URL, timeout=30.0) as client:
            all_results = []
            
            # Search each vector store
            for vector_store_id in VECTOR_STORE_IDS:
                response = await client.post(
                    f"/v1/vector_stores/{vector_store_id}/search",
                    json=payload
                )
                response.raise_for_status()
                store_results = response.json()
                
                # Track source
                for item in store_results.get('data', []):
                    item['_vector_store_id'] = vector_store_id
                    all_results.append(item)
            
            if not all_results:
                return "No relevant documentation found."
            
            # Combine and sort by score
            if COMBINE_RESULTS and len(VECTOR_STORE_IDS) > 1:
                all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            all_results = all_results[:MAX_RESULTS]
            
            # Format results
            chunks = []
            for i, item in enumerate(all_results, 1):
                filename = item.get('filename', 'unknown')
                score = item.get('score', 0)
                content = item['content'][0]['text'] if item.get('content') else ''
                
                if len(content) > 800:
                    content = content[:800] + "..."
                
                source_info = ""
                if len(VECTOR_STORE_IDS) > 1:
                    store = item.get('_vector_store_id', '')
                    source_info = f" [store: ...{store[-12:]}]"
                
                chunks.append(
                    f"**Result {i}** (from {filename}{source_info}, score: {score:.3f})\n\n{content}"
                )
            
            return "\n\n---\n\n".join(chunks)
    
    except httpx.HTTPError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
