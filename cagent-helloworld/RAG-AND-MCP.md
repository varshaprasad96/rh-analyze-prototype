# RAG and MCP with cagent and Llama Stack

## How cagent Uses Llama Stack

**Connection:** cagent connects to Llama Stack via OpenAI-compatible API

```
cagent Agent
    ↓ (OpenAI-compatible calls)
Llama Stack (/v1/chat/completions, /v1/embeddings)
    ↓
vLLM Model (inference)
```

## RAG in cagent

### What Works

cagent has **built-in RAG** that works independently:

```yaml
rag:
  my_kb:
    docs: ["/data/docs"]  # LOCAL files in cagent container
    strategies:
      - type: chunked-embeddings
        embedding_model: llama-stack/text-embedding  # Uses Llama Stack for embeddings
        database: ./rag.db  # LOCAL SQLite in cagent pod
        vector_dimensions: 768
```

**Flow:**
1. cagent loads docs from container filesystem
2. Calls Llama Stack `/v1/embeddings` for vectors
3. Stores vectors in local SQLite
4. Searches locally at query time
5. Enriches prompt with retrieved chunks
6. Sends to Llama Stack `/v1/chat/completions`

### What Doesn't Work

- ❌ cagent cannot use Llama Stack's Milvus vector store
- ❌ `builtin::rag` toolset doesn't exist in cagent
- ❌ The `vs_*` vector store we created is unused by cagent

**Why:** cagent and Llama Stack have separate RAG systems that don't communicate.

## MCP in cagent

### What Works

cagent can call external MCP servers:

```yaml
toolsets:
  - type: mcp
    remote:
      url: "https://api.example.com/mcp"
      transport_type: "http"
      headers:
        Authorization: "Bearer ${TOKEN}"
```

**Flow:**
1. Agent decides to use MCP tool
2. cagent sends MCP protocol request
3. Remote MCP server processes
4. Result returned to agent

### What Doesn't Work

- ❌ Llama Stack's vector store is not exposed as MCP
- ❌ GitHub Copilot MCP URL needs verification
- ❌ MCP tools need to follow the MCP protocol spec

## Current Agent Configuration

### What's Deployed
- ✅ Agent connects to Llama Stack for LLM inference
- ✅ Vector store exists in Llama Stack (unused)
- ✅ GitHub MCP token configured (not working yet)

### What's Missing
- ❌ No local docs in cagent container for RAG
- ❌ No working MCP integration
- ❌ Agent only has basic LLM access

## To Enable RAG

**Option 1: Use cagent's Native RAG**
1. Download the 6 markdown files into cagent container
2. Configure cagent RAG with local paths
3. Use Llama Stack only for embeddings + inference

**Option 2: Use Llama Stack Agents API**
1. Skip cagent
2. Use Llama Stack's native Agents API
3. Has built-in RAG with vector store support

## To Enable MCP

**Option 1: Verify GitHub MCP**
- Confirm the GitHub Copilot MCP endpoint is correct
- Test token authentication
- Check MCP protocol version

**Option 2: Create Custom MCP Server**
- Wrap Llama Stack's RAG API as MCP
- Expose vector store via MCP protocol
- cagent can then call it

## Recommendation

**For this POC:**
- Use cagent for simple agents (no RAG)
- Use Llama Stack Agents API for agents needing RAG
- Use kagent (next phase) for Kubernetes-native agents with better RAG integration

**Current State:**
- Basic cagent agent working ✅
- Llama Stack working ✅
- Vector store populated but unused ⚠️
- RAG/MCP needs architecture decision 🤔

