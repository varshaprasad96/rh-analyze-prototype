# Kagenti Deployment

Kagenti is a cloud-native middleware platform that provides framework-neutral, scalable, and secure infrastructure for deploying and orchestrating AI agents through standardized REST APIs.

## Understanding kagent vs kagenti

| Component | CRD API Group | Purpose | Default Port |
|-----------|---------------|---------|--------------|
| **kagent** | `kagent.dev/v1alpha2` | Framework for building AI agents with ADK | 8080 |
| **kagenti** | `agent.kagenti.dev/v1alpha1` | Multi-agent orchestration platform | 8000 |

Both support A2A protocol but have different CRDs and management patterns.

## Quick Start - Standalone UI

For testing without the full kagenti stack, deploy just the UI:

```bash
make deploy-kagenti-ui NAMESPACE=mschimun
```

This deploys kagenti-ui without authentication, allowing you to:
- Browse and manage A2A agents
- Discover MCP tools
- Test agents interactively

**Access:** https://kagenti-ui-mschimun.apps.rosa.mschimun.072j.p3.openshiftapps.com

Or via port-forward:
```bash
oc port-forward -n mschimun svc/kagenti-ui 8501:8501
open http://localhost:8501
```

### Standalone UI Requirements

For the UI to discover agents:

1. **Label the namespace:**
   ```bash
   oc label namespace mschimun kagenti-enabled=true
   ```

2. **Agents must have labels:**
   ```yaml
   labels:
     kagenti.io/type: agent
     kagenti.io/agent-protocol: a2a  # For AgentCard sync
   ```

3. **Service must be accessible on port 8000** (kagenti default)

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                           Kubernetes Cluster                          │
├───────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                      kagenti-system Namespace                   │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐ │  │
│  │  │ Kagenti UI │  │  Agent     │  │  Ingress   │  │   Kiali    │ │  │
│  │  │            │  │  Lifecycle │  │  Gateway   │  │            │ │  │
│  │  │            │  │  Operator  │  │            │  │            │ │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                Workload Namespaces (team1, team2, ...)           │ │
│  │     ┌──────────────┐  ┌──────────────┐   ┌──────────────┐        │ │
│  │     │  A2A Agents  │  │  MCP Tools   │   │ Custom       │        │ │
│  │     │  (kagent,    │  │  (GitHub,    │   │ Workloads    │        │ │
│  │     │   MLflow,    │  │   vector     │   │              │        │ │
│  │     │   etc.)      │  │   search)    │   │              │        │ │
│  │     └──────────────┘  └──────────────┘   └──────────────┘        │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│    ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐     │
│    │     SPIRE      │  │   Keycloak     │  │  Istio Ambient     │     │
│    │  (Identity)    │  │     (IAM)      │  │  (Service Mesh)    │     │
│    └────────────────┘  └────────────────┘  └────────────────────┘     │
└───────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### OpenShift-Specific Requirements

| Tool | Purpose |
|------|---------|
| oc | ≥4.16.0 (OpenShift CLI) |
| kubectl | ≥1.32.1 |
| Helm | ≥3.18.0 |
| OpenShift cluster | Admin access required (tested with OpenShift 4.19) |

### Pre-Installation Steps

#### 1. Remove Cert Manager (if installed)

Kagenti installs its own Cert Manager. Remove any existing installation:

```bash
# Check if cert-manager exists
kubectl get all -n cert-manager-operator
kubectl get all -n cert-manager

# If present, uninstall via OpenShift Console or CLI
kubectl delete deploy cert-manager cert-manager-cainjector cert-manager-webhook -n cert-manager
kubectl delete service cert-manager cert-manager-cainjector cert-manager-webhook -n cert-manager
kubectl delete ns cert-manager-operator cert-manager
```

#### 2. Configure OVN for Istio Ambient Mode

```bash
# Check network type
kubectl describe network.config/cluster

# If using OVNKubernetes, enable local gateway mode
kubectl patch network.operator.openshift.io cluster --type=merge \
  -p '{"spec":{"defaultNetwork":{"ovnKubernetesConfig":{"gatewayConfig":{"routingViaHost":true}}}}}'
```

## Installation

### Step 1: Configure Secrets

```bash
# Copy secrets template
cp secrets.yaml.template secrets.yaml

# Edit secrets.yaml with your values:
# - GITHUB_USER: Your GitHub username
# - GITHUB_TOKEN: Your GitHub personal access token
# - OPENAI_API_KEY: OpenAI API key (required for OpenShift as Ollama not yet available)
```

### Step 2: Set Trust Domain

```bash
export DOMAIN=apps.$(kubectl get dns cluster -o jsonpath='{ .spec.baseDomain }')
echo "Trust domain: $DOMAIN"
```

### Step 3: Install Dependencies (kagenti-deps)

```bash
# Get latest version
LATEST_TAG=$(git ls-remote --tags --sort="v:refname" https://github.com/kagenti/kagenti.git | tail -n1 | sed 's|.*refs/tags/v||; s/\^{}//')
echo "Installing version: $LATEST_TAG"

# Install dependencies
helm install --create-namespace -n kagenti-system kagenti-deps \
  oci://ghcr.io/kagenti/kagenti/kagenti-deps \
  --version $LATEST_TAG \
  --set spire.trustDomain=${DOMAIN} \
  --wait
```

### Step 4: Install MCP Gateway

```bash
# Get latest MCP Gateway version
LATEST_GATEWAY_TAG=$(skopeo list-tags docker://ghcr.io/kagenti/charts/mcp-gateway | jq -r '.Tags[-1]')

# Install MCP Gateway
helm install mcp-gateway oci://ghcr.io/kagenti/charts/mcp-gateway \
  --create-namespace --namespace mcp-system \
  --version $LATEST_GATEWAY_TAG
```

### Step 5: Install Kagenti

```bash
# Install Kagenti with OpenShift CA workaround
helm upgrade --install --create-namespace -n kagenti-system \
  -f secrets.yaml kagenti oci://ghcr.io/kagenti/kagenti/kagenti \
  --version $LATEST_TAG \
  --set agentOAuthSecret.spiffePrefix=spiffe://${DOMAIN}/sa \
  --set uiOAuthSecret.useServiceAccountCA=false \
  --set agentOAuthSecret.useServiceAccountCA=false
```

## Accessing Kagenti

### UI Access

```bash
# Get UI URL
echo "https://$(kubectl get route kagenti-ui -n kagenti-system -o jsonpath='{.status.ingress[0].host}')"
```

### Default Credentials

```
Username: admin
Password: admin
```

### Keycloak Admin

```bash
kubectl get secret keycloak-initial-admin -n keycloak \
  -o go-template='Username: {{.data.username | base64decode}}  Password: {{.data.password | base64decode}}{{"\\n"}}'
```

## Verification

### Check SPIRE Daemonsets

```bash
kubectl get daemonsets -n zero-trust-workload-identity-manager
```

### Check All Components

```bash
# kagenti-system
kubectl get pods -n kagenti-system

# Keycloak
kubectl get pods -n keycloak

# MCP System
kubectl get pods -n mcp-system

# SPIRE
kubectl get pods -n zero-trust-workload-identity-manager

# Istio
kubectl get pods -n istio-system
```

## Integrating kagent.dev Agents with kagenti

The challenge: kagent.dev agents run on port 8080, but kagenti-ui expects port 8000.

### Option 1: Use kagent-ui (Recommended)

The simplest approach is to use the dedicated kagent-ui for kagent.dev agents:

```bash
# kagent-ui URL (deployed with kagent)
https://kagent-ui-kagent.apps.rosa.<cluster>/
```

This UI natively supports `kagent.dev` CRDs and doesn't have port mismatch issues.

### Option 2: Create Port Alias Service

Create a service that maps port 8000 → 8080:

```yaml
# File: kagenti-service-alias.yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-kagent-kagenti
  namespace: mschimun
  labels:
    kagenti.io/type: agent
spec:
  selector:
    app: kagent
    kagent: hello-kagent
  ports:
    - name: http
      port: 8000        # kagenti expects this
      targetPort: 8080  # kagent uses this
```

### Option 3: Create agent.kagenti.dev Wrapper

For full integration with kagenti-operator:

```yaml
# File: hello-kagent-kagenti-agent.yaml
apiVersion: agent.kagenti.dev/v1alpha1
kind: Agent
metadata:
  name: hello-kagent
  namespace: mschimun
  labels:
    kagenti.io/type: agent
    kagenti.io/agent-protocol: a2a
    kagenti.io/framework: kagent
    app.kubernetes.io/name: hello-kagent
spec:
  replicas: 0  # Don't create new pods
  imageSource:
    image: "cr.kagent.dev/kagent-dev/kagent/app:0.7.7"
  servicePorts:
    - port: 8000
      targetPort: 8080
      protocol: TCP
      name: http
  podTemplateSpec:
    spec:
      containers:
        - name: agent
          image: "cr.kagent.dev/kagent-dev/kagent/app:0.7.7"
          ports:
            - containerPort: 8080
```

After applying, patch the service to use existing kagent pods:

```bash
# The kagenti-operator creates hello-kagent-svc, update its selector
oc patch svc hello-kagent-svc -n mschimun --type='json' -p='[
  {"op": "replace", "path": "/spec/selector", "value": {"app": "kagent", "kagent": "hello-kagent"}}
]'
```

### Required Namespace Label

For any option, the namespace must be labeled:

```bash
oc label namespace mschimun kagenti-enabled=true
```

## Deploying kagenti-operator

The kagenti-operator manages `agent.kagenti.dev` CRDs. To install:

### Step 1: Clone the Repository

```bash
git clone https://github.com/kagenti/kagenti-operator.git
cd kagenti-operator
```

### Step 2: Install CRDs

```bash
# Install kagenti CRDs
kubectl apply -f config/crd/bases/
```

### Step 3: Deploy the Operator

```bash
# Via Helm (recommended)
LATEST_TAG=$(git ls-remote --tags --sort="v:refname" https://github.com/kagenti/kagenti-operator.git | tail -n1 | sed 's|.*refs/tags/v||; s/\^{}//')

helm install kagenti-operator oci://ghcr.io/kagenti/kagenti-operator/kagenti-operator \
  --namespace kagenti-system \
  --create-namespace \
  --version $LATEST_TAG
```

Or deploy from source:

```bash
make deploy IMG=ghcr.io/kagenti/kagenti-operator:latest
```

### Step 4: Verify Installation

```bash
# Check operator is running
kubectl get pods -n kagenti-system

# Check CRDs are installed
kubectl get crd | grep kagenti
# Should show:
# agents.agent.kagenti.dev
# agentbuilds.agent.kagenti.dev
# agentcards.agent.kagenti.dev
```

## AgentCard Discovery

The kagenti-operator automatically creates `AgentCard` resources for agents with proper labels:

```bash
# View discovered agents
kubectl get agentcards -A

# Example output:
# NAMESPACE   NAME                PROTOCOL   AGENT          SYNCED   LASTSYNC
# mschimun    hello-kagent-card   a2a        hello_kagent   True     30s
```

The AgentCard fetches agent metadata from `/.well-known/agent.json` endpoint.

## Register Existing A2A Agents

For any A2A-compatible agent (kagent, MLflow, custom):

1. **Ensure the agent exposes:**
   - `GET /.well-known/agent.json` - Agent card
   - `POST /` - A2A message endpoint

2. **Create agent.kagenti.dev resource:**
   ```yaml
   apiVersion: agent.kagenti.dev/v1alpha1
   kind: Agent
   metadata:
     name: my-agent
     labels:
       kagenti.io/type: agent
       kagenti.io/agent-protocol: a2a
   spec:
     servicePorts:
       - port: 8000
         targetPort: <agent-port>
   ```

3. **Label namespace:**
   ```bash
   kubectl label namespace <ns> kagenti-enabled=true
   ```

## Troubleshooting

### SPIRE Daemonset Issues

If daemonsets show `Current=0` or `Ready=0`:

```bash
# Check for SCC errors
kubectl describe daemonsets -n zero-trust-workload-identity-manager spire-agent

# Fix SCC if needed
oc adm policy add-scc-to-user privileged -z spire-agent -n zero-trust-workload-identity-manager
kubectl rollout restart daemonsets -n zero-trust-workload-identity-manager spire-agent

oc adm policy add-scc-to-user privileged -z spire-spiffe-csi-driver -n zero-trust-workload-identity-manager
kubectl rollout restart daemonsets -n zero-trust-workload-identity-manager spire-spiffe-csi-driver
```

### View Logs

```bash
# Kagenti UI
kubectl logs -n kagenti-system -l app=kagenti-ui -f

# Agent Lifecycle Operator
kubectl logs -n kagenti-system -l app=kagenti-operator -f

# MCP Gateway
kubectl logs -n mcp-system -l app=mcp-gateway -f
```

## Known Limitations: kagent.dev → kagenti Integration

### Challenge

Integrating `kagent.dev` agents with `kagenti-ui` is complex because:

| Issue | Description |
|-------|-------------|
| **Different CRDs** | kagent uses `kagent.dev/v1alpha2`, kagenti uses `agent.kagenti.dev/v1alpha1` |
| **Port Mismatch** | kagent runs on 8080, kagenti expects 8000 |
| **AgentCard Dependency** | AgentCard requires Agent to be "Ready" |
| **Pod Requirement** | agent.kagenti.dev needs its own running pods |

### Attempted Solutions

1. **Service alias (port 8000 → 8080)**: Works for connectivity, but AgentCard won't sync without a Ready Agent
2. **Wrapper with replicas: 0**: Agent never becomes Ready, AgentCard won't sync
3. **Wrapper with replicas: 1**: Creates duplicate pods, kagent image needs specific volume mounts

### Recommended Approach

**For kagent.dev agents**: Use **kagent-ui** (native support)
```
https://kagent-ui-kagent.apps.rosa.<cluster>/
```

**For kagenti orchestration**: Use **MLflow ResponsesAgent** with A2A wrapper
- Build a custom container with A2A endpoints
- Deploy as `agent.kagenti.dev` resource
- Full kagenti integration without conflicts

See: `../STRATEGY-COMPARISON-KAGENT-VS-MLFLOW-RESPONSESAGENT.md` for details.

## Related Documentation

- [Kagenti GitHub](https://github.com/kagenti/kagenti)
- [Installation Guide](https://github.com/kagenti/kagenti/blob/main/docs/install.md)
- [A2A Protocol](https://google.github.io/A2A)
- [MCP Protocol](https://modelcontextprotocol.io)

