# RAG and MCP with kagent and Llama Stack

## How kagent Uses Llama Stack

**Connection:** kagent uses ADK engine which calls Llama Stack via OpenAI-compatible API

```
kagent Agent (CRD) → ADK Engine → Llama Stack (/v1/chat/completions) → vLLM
```

## RAG in kagent

### What Doesn't Work

❌ **kagent has NO RAG support for Llama Stack vector stores**

**Why:**
- kagent CRD has no `rag:` or `vectorStore:` fields
- ADK calls `/v1/chat/completions` (doesn't support vector stores)
- Llama Stack's vector store needs `/v1/agents` API (not used by kagent)

**Result:**
- Vector store exists but is unused
- kagent cannot access Llama Stack's Milvus vector store
- Would need custom ADK agent code (not CRD-based)

## MCP in kagent

### What Works ✅

kagent has **excellent MCP support**:

```yaml
# 1. Create RemoteMCPServer
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: github-readonly
spec:
  url: "https://api.githubcopilot.com/mcp/x/repos/readonly"
  headersFrom:
    - name: "Authorization"
      valueFrom:
        name: github-mcp-token
        type: Secret
        key: token

# 2. Reference in Agent
spec:
  declarative:
    tools:
      - type: McpServer
        mcpServer:
          kind: RemoteMCPServer
          name: github-readonly
          toolNames: [get_file_contents, search_code, ...]
```

**Features:**
- ✅ Automatic tool discovery
- ✅ Token authentication via Secrets
- ✅ 11 GitHub tools discovered
- ✅ Kubernetes-native management

## Comparison: cagent vs kagent

**RAG:**
- cagent: ✅ Has RAG (local docs + vectors)
- kagent: ❌ No RAG (API limitation)

**MCP:**
- cagent: ⚠️ Manual configuration
- kagent: ✅ Auto-discovery, CRD-based

**Deployment:**
- cagent: Container + manual Deployment
- kagent: CRD + controller manages everything

## Current Status

**hello-kagent agent:**
- ✅ LLM inference via Llama Stack
- ✅ GitHub MCP with 11 tools
- ❌ Cannot use vector store
- ✅ kagent UI for interaction

**Recommendation:**
- Use kagent for MCP tool integration
- Cannot use for RAG with Llama Stack vector stores
- For RAG: Use cagent with local docs or Llama Stack Agents API directly
