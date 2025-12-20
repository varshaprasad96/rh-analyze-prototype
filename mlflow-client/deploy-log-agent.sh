#!/bin/bash
# Deploy script for logging agent to MLflow in cluster
# Supports both ConfigMap and Dockerfile approaches

set -e

NAMESPACE="${NAMESPACE:-rh-analyze}"
APPROACH="${APPROACH:-configmap}"  # or "docker"

echo "Deploying MLflow Agent Logger to namespace: ${NAMESPACE}"
echo "Approach: ${APPROACH}"

cd "$(dirname "$0")/.."

if [ "${APPROACH}" == "configmap" ]; then
    echo ""
    echo "=== ConfigMap Approach ==="
    echo "Creating ConfigMap with agent wrapper..."
    
    # Create ConfigMap with agent wrapper file
    # Note: The Job expects this file in the mlflow-agent-logger-scripts ConfigMap
    # So we need to add it to that ConfigMap, not create a separate one
    oc create configmap mlflow-agent-wrapper-direct \
        --from-file=llamastack_agent_wrapper_direct.py=mlflow-client/llamastack_agent_wrapper_direct.py \
        -n "${NAMESPACE}" \
        --dry-run=client -o yaml | oc apply -f -
    
    # Also add it to the logger scripts ConfigMap (which the Job uses)
    oc create configmap mlflow-agent-logger-scripts \
        --from-file=llamastack_agent_wrapper_direct.py=mlflow-client/llamastack_agent_wrapper_direct.py \
        --from-file=log_llamastack_agent_direct.py=mlflow-client/log_llamastack_agent_direct.py \
        -n "${NAMESPACE}" \
        --dry-run=client -o yaml | oc apply -f -
    
    echo "✓ ConfigMap created"
    echo ""
    echo "Deploying Job with ConfigMap..."
    oc apply -f deployment-yamls/log-agent-job.yaml
    
elif [ "${APPROACH}" == "docker" ]; then
    echo ""
    echo "=== Dockerfile Approach ==="
    echo "Building Docker image..."
    
    # Build and push image
    ./mlflow-client/build-and-deploy.sh
    
    echo ""
    echo "Update deployment-yamls/log-agent-job-docker.yaml with your image name, then:"
    echo "  oc apply -f deployment-yamls/log-agent-job-docker.yaml"
    
else
    echo "Unknown approach: ${APPROACH}"
    echo "Use APPROACH=configmap or APPROACH=docker"
    exit 1
fi

echo ""
echo "Waiting for Job to start..."
sleep 3

echo ""
echo "Checking Job status:"
oc get job mlflow-log-agent-direct -n "${NAMESPACE}"

echo ""
echo "To view logs:"
echo "  oc logs -f job/mlflow-log-agent-direct -n ${NAMESPACE}"

echo ""
echo "To view in MLflow UI (after port-forwarding):"
echo "  oc port-forward svc/mlflow 5000:5000 -n ${NAMESPACE}"
echo "  Then open: http://localhost:5000"

