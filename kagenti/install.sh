#!/bin/bash
# Kagenti Installation Script for OpenShift
# Usage: ./install.sh [--skip-deps] [--skip-mcp-gateway] [--skip-kagenti]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
SKIP_DEPS=false
SKIP_MCP_GATEWAY=false
SKIP_KAGENTI=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-deps) SKIP_DEPS=true; shift ;;
        --skip-mcp-gateway) SKIP_MCP_GATEWAY=true; shift ;;
        --skip-kagenti) SKIP_KAGENTI=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v oc &> /dev/null; then
    log_error "oc CLI not found. Please install OpenShift CLI."
    exit 1
fi

if ! command -v helm &> /dev/null; then
    log_error "helm not found. Please install Helm."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl."
    exit 1
fi

# Check if logged in
if ! oc whoami &> /dev/null; then
    log_error "Not logged into OpenShift. Please run 'oc login' first."
    exit 1
fi

log_info "Prerequisites check passed."

# Check for secrets file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "${SCRIPT_DIR}/secrets.yaml" ]; then
    log_warn "secrets.yaml not found!"
    log_info "Creating from template..."
    cp "${SCRIPT_DIR}/secrets.yaml.template" "${SCRIPT_DIR}/secrets.yaml"
    log_warn "Please edit ${SCRIPT_DIR}/secrets.yaml with your credentials and run again."
    exit 1
fi

# Get trust domain
log_info "Getting trust domain..."
DOMAIN=$(kubectl get dns cluster -o jsonpath='{ .spec.baseDomain }')
if [ -z "$DOMAIN" ]; then
    log_error "Could not determine cluster domain."
    exit 1
fi
DOMAIN="apps.${DOMAIN}"
log_info "Trust domain: ${DOMAIN}"

# Get latest version
log_info "Getting latest kagenti version..."
LATEST_TAG=$(git ls-remote --tags --sort="v:refname" https://github.com/kagenti/kagenti.git | tail -n1 | sed 's|.*refs/tags/v||; s/\^{}//')
if [ -z "$LATEST_TAG" ]; then
    log_warn "Could not determine latest version, using v0.2.0-alpha.2"
    LATEST_TAG="0.2.0-alpha.2"
fi
log_info "Using version: ${LATEST_TAG}"

# Step 1: Install Dependencies
if [ "$SKIP_DEPS" = false ]; then
    log_info "Installing kagenti-deps..."
    helm upgrade --install --create-namespace -n kagenti-system kagenti-deps \
        oci://ghcr.io/kagenti/kagenti/kagenti-deps \
        --version ${LATEST_TAG} \
        -f "${SCRIPT_DIR}/values-deps-openshift.yaml" \
        --set spire.trustDomain=${DOMAIN} \
        --wait --timeout 10m
    log_info "kagenti-deps installed successfully."
else
    log_info "Skipping kagenti-deps installation."
fi

# Step 2: Install MCP Gateway
if [ "$SKIP_MCP_GATEWAY" = false ]; then
    log_info "Installing MCP Gateway..."
    
    # Try to get latest gateway version, fall back to 0.4.0
    if command -v skopeo &> /dev/null; then
        LATEST_GATEWAY_TAG=$(skopeo list-tags docker://ghcr.io/kagenti/charts/mcp-gateway 2>/dev/null | jq -r '.Tags[-1]' 2>/dev/null || echo "0.4.0")
    else
        LATEST_GATEWAY_TAG="0.4.0"
    fi
    log_info "Using MCP Gateway version: ${LATEST_GATEWAY_TAG}"
    
    helm upgrade --install mcp-gateway oci://ghcr.io/kagenti/charts/mcp-gateway \
        --create-namespace --namespace mcp-system \
        --version ${LATEST_GATEWAY_TAG} \
        --wait --timeout 5m
    log_info "MCP Gateway installed successfully."
else
    log_info "Skipping MCP Gateway installation."
fi

# Step 3: Install Kagenti
if [ "$SKIP_KAGENTI" = false ]; then
    log_info "Installing kagenti..."
    helm upgrade --install --create-namespace -n kagenti-system \
        -f "${SCRIPT_DIR}/secrets.yaml" \
        -f "${SCRIPT_DIR}/values-openshift.yaml" \
        kagenti oci://ghcr.io/kagenti/kagenti/kagenti \
        --version ${LATEST_TAG} \
        --set agentOAuthSecret.spiffePrefix=spiffe://${DOMAIN}/sa \
        --set uiOAuthSecret.useServiceAccountCA=false \
        --set agentOAuthSecret.useServiceAccountCA=false \
        --wait --timeout 10m
    log_info "kagenti installed successfully."
else
    log_info "Skipping kagenti installation."
fi

# Verify installation
log_info "Verifying installation..."

echo ""
echo "=== SPIRE Daemonsets ==="
kubectl get daemonsets -n zero-trust-workload-identity-manager 2>/dev/null || echo "SPIRE not ready yet"

echo ""
echo "=== Kagenti System ==="
kubectl get pods -n kagenti-system 2>/dev/null || echo "kagenti-system not ready yet"

echo ""
echo "=== MCP System ==="
kubectl get pods -n mcp-system 2>/dev/null || echo "mcp-system not ready yet"

echo ""
log_info "Installation complete!"
echo ""
echo "Access the UI:"
echo "  URL: https://$(kubectl get route kagenti-ui -n kagenti-system -o jsonpath='{.status.ingress[0].host}' 2>/dev/null || echo 'kagenti-ui.<cluster-domain>')"
echo "  Credentials: admin / admin"
echo ""
echo "If SPIRE daemonsets show 0/0, run:"
echo "  oc adm policy add-scc-to-user privileged -z spire-agent -n zero-trust-workload-identity-manager"
echo "  kubectl rollout restart daemonsets -n zero-trust-workload-identity-manager"


