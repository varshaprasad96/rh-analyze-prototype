"""
FastMCP Vector Search Server

Generic MCP server that reads configuration from ConfigMap environment variables.
Exposes Llama Stack vector store search. LLM only provides the search query.
"""
import json
import os
import httpx
from fastmcp import FastMCP

# OpenTelemetry imports (optional - graceful fallback if not available)
OTEL_ENABLED = False
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "vector-search-mcp")

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    
    if OTEL_ENDPOINT:
        print(f"  OTEL Endpoint: {OTEL_ENDPOINT}")
        resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        OTEL_ENABLED = True
        print(f"  OTEL tracing enabled")
    else:
        print(f"  OTEL tracing disabled (no endpoint configured)")
except ImportError as e:
    print(f"  OTEL tracing disabled (missing dependencies: {e})")
    # Create a no-op tracer for when OTEL is not available
    class NoOpSpan:
        def set_attribute(self, key, value): pass
        def record_exception(self, e): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    class NoOpTracer:
        def start_as_current_span(self, name): return NoOpSpan()
    
    class NoOpTrace:
        @staticmethod
        def get_tracer(name): return NoOpTracer()

# Get tracer (real or no-op depending on OTEL availability)
if OTEL_ENABLED:
    tracer = trace.get_tracer(__name__)
else:
    tracer = NoOpTrace.get_tracer(__name__)

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
    # Create a span for the entire tool invocation
    with tracer.start_as_current_span("search_knowledge_base") as span:
        span.set_attribute("query", query)
        span.set_attribute("vector_store_count", len(VECTOR_STORE_IDS))
        span.set_attribute("max_results", MAX_RESULTS)
        span.set_attribute("search_mode", SEARCH_MODE)
        
        if not VECTOR_STORE_IDS:
            span.set_attribute("error", "no_vector_stores_configured")
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
                    with tracer.start_as_current_span(f"search_vector_store") as store_span:
                        store_span.set_attribute("vector_store_id", vector_store_id)
                        
                        response = await client.post(
                            f"/v1/vector_stores/{vector_store_id}/search",
                            json=payload
                        )
                        response.raise_for_status()
                        store_results = response.json()
                        
                        result_count = len(store_results.get('data', []))
                        store_span.set_attribute("result_count", result_count)
                        
                        # Track source
                        for item in store_results.get('data', []):
                            item['_vector_store_id'] = vector_store_id
                            all_results.append(item)
                
                span.set_attribute("total_results", len(all_results))
                
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
                
                span.set_attribute("returned_results", len(chunks))
                return "\n\n---\n\n".join(chunks)
        
        except httpx.HTTPError as e:
            span.set_attribute("error", str(e))
            span.record_exception(e)
            return f"Error: {str(e)}"
        except Exception as e:
            span.set_attribute("error", str(e))
            span.record_exception(e)
            return f"Error: {str(e)}"
