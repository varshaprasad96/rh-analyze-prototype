# MCP (Model Context Protocol) Integration

Configuration for MCP server integrations with the multi-agent platform.

## GitHub MCP Server

Integrates GitHub Copilot's MCP server to enable agents to access GitHub repositories in read-only mode.

### Files

- **`github-secret.yaml`** - Secret template for GitHub token (uses GITHUB_TOKEN_PLACEHOLDER)

### Setup

The GitHub token is automatically deployed as part of the `make deploy` flow.

### Token Management

**Local development:**
1. Add your GitHub token to `.env.local`:
   ```bash
   GITHUB_MCP_TOKEN=your-github-token-here
   ```

2. The Makefile automatically creates the Secret in OpenShift during deployment

**Manual deployment:**
```bash
# Export token from .env.local
source .env.local

# Create secret
sed "s/NAMESPACE_PLACEHOLDER/my-namespace/g" github-secret.yaml | \
  sed "s/GITHUB_TOKEN_PLACEHOLDER/$GITHUB_MCP_TOKEN/g" | \
  oc apply -f -
```

### GitHub MCP Endpoint

**URL:** `https://api.githubcopilot.com/mcp/x/repos/readonly`

**Capabilities:**
- Read repository contents
- Search code
- Access file contents
- List repositories (read-only access)

### Agent Integration

Agents reference the GitHub token via environment variable:

```yaml
# In agent.yaml
toolsets:
  - type: mcp
    remote:
      url: "https://api.githubcopilot.com/mcp/x/repos/readonly"
      transport_type: "http"
```

The agent deployment automatically injects the `GITHUB_MCP_TOKEN` from the Secret.

### Verification

Check the secret was created:

```bash
oc get secret github-mcp-token -n my-namespace
oc get secret github-mcp-token -n my-namespace -o jsonpath='{.data.token}' | base64 -d
```

### Security

- Token stored as OpenShift Secret (encrypted at rest)
- Not exposed in Git (`.env.local` is git-ignored)
- Pod-level access only
- Read-only access to GitHub

### Troubleshooting

**Secret not found:**
```bash
# Manually create the secret
make deploy-mcp-secrets NAMESPACE=my-namespace
```

**Token invalid:**
- Verify token in `.env.local`
- Check token has appropriate GitHub permissions
- Regenerate token if expired

**Agent can't access MCP:**
- Check agent logs: `oc logs -n my-namespace -l app=hello-agent -c cagent`
- Verify secret exists: `oc get secret github-mcp-token -n my-namespace`
- Check network connectivity to GitHub API

