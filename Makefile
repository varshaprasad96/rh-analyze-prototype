.PHONY: login logout whoami projects console help deploy deploy-vllm deploy-llamastack deploy-agent build-agent clean status

# Load environment variables from .env.local
include .env.local
export

# Default namespace if not specified
NAMESPACE ?= mschimun

help:
	@echo "Available commands:"
	@echo ""
	@echo "Cluster Management:"
	@echo "  make login              - Log into OpenShift cluster"
	@echo "  make logout             - Log out from OpenShift cluster"
	@echo "  make whoami             - Show current user and cluster info"
	@echo "  make projects           - List all available projects"
	@echo "  make console            - Display console URL"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy NAMESPACE=<name>       - Deploy complete stack (vLLM + Llama Stack + Agent)"
	@echo "  make deploy-vllm NAMESPACE=<name>  - Deploy only vLLM model"
	@echo "  make deploy-llamastack NAMESPACE=<name> - Deploy only Llama Stack"
	@echo "  make build-agent NAMESPACE=<name>  - Build agent image on cluster"
	@echo "  make deploy-agent NAMESPACE=<name> - Deploy hello-agent"
	@echo "  make status NAMESPACE=<name>       - Check deployment status"
	@echo "  make clean NAMESPACE=<name>        - Remove deployments from namespace"
	@echo ""
	@echo "Default namespace: $(NAMESPACE)"

login:
	@echo "Logging into OpenShift cluster..."
	@oc login --server=$(OCP_SERVER) \
		--username=$(OCP_USERNAME) \
		--password='$(OCP_PASSWORD)' \
		--insecure-skip-tls-verify
	@echo "✓ Successfully logged in as $(OCP_USERNAME)"

logout:
	@echo "Logging out from OpenShift cluster..."
	@oc logout
	@echo "✓ Logged out"

whoami:
	@echo "Current user:"
	@oc whoami
	@echo ""
	@echo "Cluster version:"
	@oc version
	@echo ""
	@echo "Current project:"
	@oc project

projects:
	@echo "Available projects:"
	@oc projects

console:
	@echo "OpenShift Console URL:"
	@echo "$(OCP_CONSOLE)"

# Deployment targets
deploy: deploy-vllm build-agent deploy-llamastack deploy-agent
	@echo ""
	@echo "✓ Complete deployment in namespace: $(NAMESPACE)"
	@echo ""
	@echo "Endpoints:"
	@echo "  - vLLM:        http://qwen3-14b-awq-predictor.$(NAMESPACE).svc.cluster.local:8080"
	@echo "  - Llama Stack: http://llama-stack-service.$(NAMESPACE).svc.cluster.local:8321"
	@echo "  - Hello Agent: http://hello-agent.$(NAMESPACE).svc.cluster.local:8080"
	@echo ""
	@echo "See cagent-helloworld/README.md for testing instructions"

deploy-vllm:
	@echo "Deploying vLLM model to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Checking if namespace exists..."
	@oc get namespace $(NAMESPACE) >/dev/null 2>&1 || \
		(echo "  Namespace does not exist. Creating..." && \
		 oc create namespace $(NAMESPACE) && \
		 echo "  ✓ Namespace created")
	@echo ""
	@echo "→ Creating ServingRuntime..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' vllm/servingruntime.yaml | oc apply -f -
	@echo "  ✓ ServingRuntime applied"
	@echo ""
	@echo "→ Creating model connection secret..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' vllm/secret.yaml | oc apply -f -
	@echo "  ✓ Secret applied"
	@echo ""
	@echo "→ Deploying vLLM InferenceService..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' vllm/inferenceservice.yaml | oc apply -f -
	@echo "  ✓ InferenceService applied"
	@echo ""
	@echo "→ Waiting for vLLM model to be ready (this may take 15-20 minutes for initial download)..."
	@timeout 1200 bash -c 'until oc get inferenceservice qwen3-14b-awq -n $(NAMESPACE) -o jsonpath="{.status.conditions[?(@.type==\"Ready\")].status}" 2>/dev/null | grep -q "True"; do echo "  Waiting for model to load..."; sleep 15; done' || \
		(echo "  ⚠ Timeout waiting for vLLM. Check status with: make status NAMESPACE=$(NAMESPACE)" && exit 0)
	@echo "  ✓ vLLM model is ready"

deploy-llamastack:
	@echo ""
	@echo "Deploying Llama Stack to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating Llama Stack ConfigMap..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' llamastack/configmap-template.yaml | oc apply -f -
	@echo "  ✓ ConfigMap applied"
	@echo ""
	@echo "→ Deploying LlamaStackDistribution..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' llamastack/llamastackdistribution.yaml | oc apply -f -
	@echo "  ✓ LlamaStackDistribution applied"
	@echo ""
	@echo "→ Waiting for Llama Stack to be ready..."
	@timeout 300 bash -c 'until oc get pods -n $(NAMESPACE) -l app=llama-stack -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for Llama Stack pod..."; sleep 5; done' || \
		(echo "  ⚠ Timeout waiting for Llama Stack. Check status with: make status NAMESPACE=$(NAMESPACE)" && exit 0)
	@echo "  ✓ Llama Stack is ready"

build-agent:
	@echo ""
	@echo "Building hello-agent image in namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating BuildConfig and ImageStream..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' cagent-helloworld/buildconfig.yaml | oc apply -f -
	@echo "  ✓ BuildConfig created"
	@echo ""
	@echo "→ Preparing agent configuration..."
	@cp cagent-helloworld/agent.yaml cagent-helloworld/agent.yaml.bak
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' cagent-helloworld/agent.yaml.bak > cagent-helloworld/agent.yaml
	@echo "  ✓ Configuration prepared"
	@echo ""
	@echo "→ Starting image build (running in background)..."
	@(cd cagent-helloworld && oc start-build hello-agent -n $(NAMESPACE) --from-dir=. --follow > /tmp/build-$(NAMESPACE).log 2>&1 && \
	  mv agent.yaml.bak agent.yaml && \
	  echo "  ✓ Build complete" || (mv agent.yaml.bak agent.yaml 2>/dev/null; echo "  ⚠ Build failed. Check: cat /tmp/build-$(NAMESPACE).log")) &
	@echo "  Build started in background"

deploy-agent:
	@echo ""
	@echo "Deploying hello-agent to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Waiting for agent image build to complete..."
	@timeout 600 bash -c 'until oc get imagestream hello-agent -n $(NAMESPACE) -o jsonpath="{.status.tags[0].items[0].dockerImageReference}" 2>/dev/null | grep -q "sha256:"; do echo "  Waiting for image build..."; sleep 10; done'
	@echo "  ✓ Agent image is ready"
	@echo ""
	@echo "→ Deploying hello-agent..."
	@AGENT_IMAGE=$$(oc get imagestream hello-agent -n $(NAMESPACE) -o jsonpath='{.status.tags[0].items[0].dockerImageReference}'); \
	sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' cagent-helloworld/deployment.yaml | \
	sed "s|your-registry/hello-agent:v1|$$AGENT_IMAGE|g" | oc apply -f -
	@echo "  ✓ Agent deployed"
	@echo ""
	@echo "→ Waiting for agent to be ready..."
	@timeout 120 bash -c 'until oc get pods -n $(NAMESPACE) -l app=hello-agent -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for agent pod..."; sleep 5; done'
	@timeout 60 bash -c 'until oc get pods -n $(NAMESPACE) -l app=hello-agent -o jsonpath="{.items[0].status.containerStatuses[0].ready}" 2>/dev/null | grep -q "true"; do echo "  Waiting for agent readiness..."; sleep 3; done'
	@echo "  ✓ Agent is ready"

status:
	@echo "Deployment status in namespace: $(NAMESPACE)"
	@echo ""
	@echo "=== vLLM Model ==="
	@oc get inferenceservice qwen3-14b-awq -n $(NAMESPACE) 2>/dev/null || echo "  Not deployed"
	@echo ""
	@echo "=== vLLM Pods ==="
	@oc get pods -n $(NAMESPACE) -l serving.kserve.io/inferenceservice=qwen3-14b-awq 2>/dev/null || echo "  No pods found"
	@echo ""
	@echo "=== Llama Stack Distribution ==="
	@oc get llamastackdistribution -n $(NAMESPACE) 2>/dev/null || echo "  Not deployed"
	@echo ""
	@echo "=== Llama Stack Pods ==="
	@oc get pods -n $(NAMESPACE) -l app=llama-stack 2>/dev/null || echo "  No pods found"
	@echo ""
	@echo "=== Hello Agent ==="
	@oc get deployment hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  Not deployed"
	@oc get pods -n $(NAMESPACE) -l app=hello-agent 2>/dev/null || echo ""
	@echo ""
	@echo "=== Services ==="
	@oc get svc -n $(NAMESPACE) | grep -E "(qwen3-14b-awq|llama-stack|hello-agent)" || echo "  No services found"

clean:
	@echo "Removing deployments from namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Removing Hello Agent..."
	@oc delete deployment hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  Deployment not found"
	@oc delete service hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  Service not found"
	@oc delete buildconfig hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  BuildConfig not found"
	@oc delete imagestream hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  ImageStream not found"
	@echo ""
	@echo "→ Removing Llama Stack..."
	@oc delete llamastackdistribution llama-stack -n $(NAMESPACE) 2>/dev/null || echo "  LlamaStackDistribution not found"
	@oc delete configmap llama-stack-config -n $(NAMESPACE) 2>/dev/null || echo "  ConfigMap not found"
	@echo ""
	@echo "→ Removing vLLM model..."
	@oc delete inferenceservice qwen3-14b-awq -n $(NAMESPACE) 2>/dev/null || echo "  InferenceService not found"
	@echo ""
	@echo "✓ Cleanup complete"
	@echo ""
	@echo "Note: Namespace '$(NAMESPACE)' was not deleted. To delete it:"
	@echo "  oc delete namespace $(NAMESPACE)"

