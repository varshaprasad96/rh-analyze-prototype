#!/bin/bash
# Build and deploy script for MLflow Agent Logger Docker image

set -e

# Configuration
NAMESPACE="${NAMESPACE:-rh-analyze}"
IMAGE_NAME="${IMAGE_NAME:-mlflow-agent-logger}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-image-registry.openshift-image-registry.svc:5000/${NAMESPACE}}"

# Full image reference
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Building Docker image: ${FULL_IMAGE}"
echo "Namespace: ${NAMESPACE}"

# Build the Docker image
docker build -t "${FULL_IMAGE}" -f Dockerfile .

# If using OpenShift internal registry, tag and push
if [[ "${REGISTRY}" == *"openshift-image-registry"* ]]; then
    echo "Tagging for OpenShift internal registry..."
    docker tag "${FULL_IMAGE}" "${FULL_IMAGE}"
    
    echo "Pushing to OpenShift registry..."
    # Login to OpenShift registry (requires oc login)
    oc registry login
    
    docker push "${FULL_IMAGE}"
    
    echo "✓ Image pushed to ${FULL_IMAGE}"
    echo ""
    echo "To deploy the Job, update deployment-yamls/log-agent-job-docker.yaml:"
    echo "  Replace 'ghcr.io/mlflow/mlflow:latest' with: ${FULL_IMAGE}"
    echo ""
    echo "Then apply:"
    echo "  oc apply -f deployment-yamls/log-agent-job-docker.yaml"
else
    echo "Using external registry. Build and push manually:"
    echo "  docker push ${FULL_IMAGE}"
fi

