.PHONY: login logout whoami projects console help deploy deploy-vllm deploy-llamastack deploy-vectorstore deploy-agent build-agent build-vectorstore deploy-mlflow deploy-otel-collector deploy-kagenti deploy-kagenti-ui deploy-kagenti-wrapper label-namespace-kagenti clean status

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
	@echo "  make deploy NAMESPACE=<name>       - Deploy complete stack (vLLM + Llama Stack + VectorStore + Agent)"
	@echo "  make deploy-vllm NAMESPACE=<name>  - Deploy only vLLM model"
	@echo "  make deploy-llamastack NAMESPACE=<name> - Deploy only Llama Stack"
	@echo "  make build-vectorstore NAMESPACE=<name> - Build vectorstore-setup image"
	@echo "  make deploy-vectorstore NAMESPACE=<name> - Setup vector store with docs"
	@echo "  make build-agent NAMESPACE=<name>  - Build agent image on cluster"
	@echo "  make deploy-agent NAMESPACE=<name> - Deploy hello-agent"
	@echo "  make status NAMESPACE=<name>       - Check deployment status"
	@echo "  make clean NAMESPACE=<name>        - Remove deployments from namespace"
	@echo ""
	@echo "Observability:"
	@echo "  make deploy-mlflow NAMESPACE=<name>        - Deploy MLflow tracking server"
	@echo "  make deploy-otel-collector NAMESPACE=<name> - Deploy OTEL collector"
	@echo ""
	@echo "Orchestration:"
	@echo "  make deploy-kagenti                              - Deploy kagenti platform (requires admin)"
	@echo "  make deploy-kagenti-ui NAMESPACE=<name>          - Deploy kagenti-ui standalone (no auth)"
	@echo "  make deploy-kagenti-wrapper NAMESPACE=<name>     - Deploy kagent→kagenti integration wrapper"
	@echo "  make label-namespace-kagenti NAMESPACE=<name>    - Label namespace for kagenti discovery"
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
deploy: deploy-vllm build-agent deploy-llamastack deploy-vectorstore deploy-agent
	@echo ""
	@echo "✓ Complete deployment in namespace: $(NAMESPACE)"
	@echo ""
	@echo "Endpoints:"
	@echo "  - vLLM:        http://qwen3-14b-awq-predictor.$(NAMESPACE).svc.cluster.local:8080"
	@echo "  - Llama Stack: http://llama-stack-service.$(NAMESPACE).svc.cluster.local:8321"
	@echo "  - Hello Agent: http://hello-agent.$(NAMESPACE).svc.cluster.local:8080"
	@echo ""
	@echo "Vector Store: docs-vectorstore (6 documentation files)"
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

build-vectorstore:
	@echo ""
	@echo "Building vectorstore-setup image in namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating BuildConfig and ImageStream..."
	@sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' llamastack/vectorstore/buildconfig.yaml | oc apply -f -
	@echo "  ✓ BuildConfig created"
	@echo ""
	@echo "→ Starting image build..."
	@cd llamastack/vectorstore && oc start-build vectorstore-setup -n $(NAMESPACE) --from-dir=. --follow
	@echo "  ✓ Image build complete"

deploy-vectorstore:
	@echo ""
	@echo "Setting up vector store in namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Checking if image exists..."
	@oc get imagestream vectorstore-setup -n $(NAMESPACE) >/dev/null 2>&1 || \
		(echo "  Image not found. Building..." && $(MAKE) build-vectorstore NAMESPACE=$(NAMESPACE))
	@echo ""
	@echo "→ Deploying vectorstore setup Job..."
	@VECTORSTORE_IMAGE=$$(oc get imagestream vectorstore-setup -n $(NAMESPACE) -o jsonpath='{.status.tags[0].items[0].dockerImageReference}'); \
	sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' llamastack/vectorstore/job.yaml | \
	sed "s|IMAGE_PLACEHOLDER|$$VECTORSTORE_IMAGE|g" | oc apply -f -
	@echo "  ✓ Job created"
	@echo ""
	@echo "→ Waiting for vector store setup to complete..."
	@timeout 300 bash -c 'until oc get job vectorstore-setup -n $(NAMESPACE) -o jsonpath="{.status.conditions[?(@.type==\"Complete\")].status}" 2>/dev/null | grep -q "True"; do echo "  Setting up vector store..."; sleep 5; done' || \
		(echo "  ⚠ Timeout waiting for vector store setup. Check logs: oc logs job/vectorstore-setup -n $(NAMESPACE)" && exit 0)
	@echo "  ✓ Vector store setup complete"
	@echo ""
	@echo "→ Creating vectorstore ConfigMap..."
	@VECTORSTORE_ID=$$(oc logs job/vectorstore-setup -n $(NAMESPACE) | grep "Vector Store ID:" | cut -d: -f2 | tr -d ' '); \
	sed 's/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g' llamastack/vectorstore/configmap.yaml | \
	sed "s/VECTORSTORE_ID_PLACEHOLDER/$$VECTORSTORE_ID/g" | oc apply -f -
	@echo "  ✓ ConfigMap created with vector store ID"

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

log-mlflow-agent:
	@echo ""
	@echo "Logging MLflow agent to tracking server in namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Checking prerequisites..."
	@$(eval VECTOR_STORE_ID := $(shell oc get configmap vectorstore-config -n $(NAMESPACE) -o jsonpath='{.data.VECTOR_STORE_ID}' 2>/dev/null))
	@if [ -z "$(VECTOR_STORE_ID)" ]; then \
		echo "  ✗ Vector store not found. Run 'make deploy-vectorstore NAMESPACE=$(NAMESPACE)' first."; \
		exit 1; \
	fi
	@echo "  ✓ Vector store found: $(VECTOR_STORE_ID)"
	@echo ""
	@echo "→ Setting up Python environment..."
	@cd mlflow-agent-helloworld && \
		python3 -m venv .venv 2>/dev/null || true && \
		. .venv/bin/activate && \
		pip install -q -r requirements.txt && \
		echo "  ✓ Dependencies installed"
	@echo ""
	@echo "→ Logging agent to MLflow..."
	@cd mlflow-agent-helloworld && \
		. .venv/bin/activate && \
		VECTOR_STORE_ID="$(VECTOR_STORE_ID)" \
		MLFLOW_TRACKING_URI="http://mlflow.$(NAMESPACE).svc.cluster.local:5000" \
		LLAMASTACK_BASE_URL="http://llama-stack-service.$(NAMESPACE).svc.cluster.local:8321" \
		python log_agent.py
	@echo ""
	@echo "  ✓ Agent logged to MLflow"

deploy-mlflow-agent:
	@echo ""
	@echo "Deploying MLflow agent helloworld to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Deploying service..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-agent-helloworld/service.yaml | oc apply -f -
	@echo "  ✓ Service deployed"
	@echo ""
	@echo "→ Deploying agent server..."
	@echo "  Note: Update MODEL_URI_PLACEHOLDER in deployment.yaml with actual model URI from MLflow"
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-agent-helloworld/deployment.yaml | oc apply -f -
	@echo "  ✓ Deployment created"
	@echo ""
	@echo "✓ MLflow agent deployed!"
	@echo ""
	@echo "Test with:"
	@echo "  oc port-forward -n $(NAMESPACE) svc/mlflow-agent-helloworld 8080:8080"
	@echo "  curl -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' -d '{\"input\": [{\"role\": \"user\", \"content\": \"What is kagent?\"}]}'"

deploy-mlflow:
	@echo ""
	@echo "Deploying MLflow stack to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating secrets..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-server/secrets.yaml | oc apply -f -
	@echo "  ✓ Secrets created"
	@echo ""
	@echo "→ Creating persistent volume claims..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-server/pvc.yaml | oc apply -f -
	@echo "  ✓ PVCs created"
	@echo ""
	@echo "→ Deploying PostgreSQL..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-server/postgres.yaml | oc apply -f -
	@echo "  ✓ PostgreSQL deployed"
	@echo ""
	@echo "→ Waiting for PostgreSQL to be ready..."
	@timeout 120 bash -c 'until oc get pods -n $(NAMESPACE) -l app=mlflow-postgres -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for PostgreSQL..."; sleep 5; done' || \
		echo "  ⚠ PostgreSQL not ready yet, continuing..."
	@echo ""
	@echo "→ Deploying MinIO..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-server/minio.yaml | oc apply -f -
	@echo "  ✓ MinIO deployed"
	@echo ""
	@echo "→ Waiting for MinIO to be ready..."
	@timeout 120 bash -c 'until oc get pods -n $(NAMESPACE) -l app=mlflow-minio -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for MinIO..."; sleep 5; done' || \
		echo "  ⚠ MinIO not ready yet, continuing..."
	@echo ""
	@echo "→ Deploying MLflow tracking server..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" mlflow-server/mlflow.yaml | oc apply -f -
	@echo "  ✓ MLflow deployed"
	@echo ""
	@echo "→ Waiting for MLflow to be ready..."
	@timeout 180 bash -c 'until oc get pods -n $(NAMESPACE) -l app=mlflow -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for MLflow..."; sleep 5; done' || \
		echo "  ⚠ MLflow not ready yet. Check: oc logs -n $(NAMESPACE) -l app=mlflow"
	@echo ""
	@echo "✓ MLflow stack deployed!"
	@echo ""
	@echo "Services:"
	@echo "  - MLflow Tracking: http://mlflow.$(NAMESPACE).svc.cluster.local:5000"
	@echo "  - MinIO API:       http://mlflow-minio.$(NAMESPACE).svc.cluster.local:9000"
	@echo "  - PostgreSQL:      mlflow-postgres.$(NAMESPACE).svc.cluster.local:5432"
	@echo ""
	@echo "Access MLflow UI:"
	@echo "  oc port-forward -n $(NAMESPACE) svc/mlflow 5000:5000"
	@echo "  open http://localhost:5000"

deploy-otel-collector:
	@echo ""
	@echo "Deploying OTEL Collector to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating ConfigMap..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" otel-collector/configmap.yaml | oc apply -f -
	@echo "  ✓ ConfigMap created"
	@echo ""
	@echo "→ Deploying OTEL Collector..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" otel-collector/deployment.yaml | oc apply -f -
	@echo "  ✓ Deployment created"
	@echo ""
	@echo "→ Creating Service..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" otel-collector/service.yaml | oc apply -f -
	@echo "  ✓ Service created"
	@echo ""
	@echo "→ Waiting for OTEL Collector to be ready..."
	@timeout 60 bash -c 'until oc get pods -n $(NAMESPACE) -l app=otel-collector -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for OTEL Collector..."; sleep 5; done' || \
		echo "  ⚠ OTEL Collector not ready yet. Check: oc logs -n $(NAMESPACE) -l app=otel-collector"
	@echo ""
	@echo "✓ OTEL Collector deployed!"
	@echo ""
	@echo "Endpoints:"
	@echo "  - OTLP gRPC: otel-collector.$(NAMESPACE).svc.cluster.local:4317"
	@echo "  - OTLP HTTP: otel-collector.$(NAMESPACE).svc.cluster.local:4318"
	@echo ""
	@echo "Configure kagent to send traces:"
	@echo "  OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.$(NAMESPACE).svc.cluster.local:4317"

deploy-kagenti:
	@echo ""
	@echo "Deploying kagenti platform..."
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Admin access to the cluster"
	@echo "  - Cert Manager uninstalled (kagenti installs its own)"
	@echo "  - OVN configured for Istio Ambient mode"
	@echo ""
	@if [ ! -f kagenti/secrets.yaml ]; then \
		echo "✗ Missing secrets.yaml!"; \
		echo "  Copy kagenti/secrets.yaml.template to kagenti/secrets.yaml"; \
		echo "  and fill in your credentials."; \
		exit 1; \
	fi
	@echo "→ Running kagenti installer..."
	@cd kagenti && ./install.sh
	@echo ""
	@echo "✓ Kagenti deployment initiated!"
	@echo ""
	@echo "Access the UI:"
	@echo "  https://$$(kubectl get route kagenti-ui -n kagenti-system -o jsonpath='{.status.ingress[0].host}' 2>/dev/null || echo 'kagenti-ui.<cluster-domain>')"
	@echo "  Credentials: admin / admin"

deploy-kagenti-skip-deps:
	@echo "Deploying kagenti (skipping dependencies)..."
	@cd kagenti && ./install.sh --skip-deps

label-namespace-kagenti:
	@echo ""
	@echo "Labeling namespace '$(NAMESPACE)' for kagenti discovery..."
	@oc label namespace $(NAMESPACE) kagenti-enabled=true --overwrite
	@echo "✓ Namespace labeled"
	@echo ""
	@echo "Namespaces with kagenti-enabled=true:"
	@oc get namespaces -l kagenti-enabled=true -o custom-columns=NAME:.metadata.name

deploy-kagenti-wrapper:
	@echo ""
	@echo "Deploying kagent→kagenti integration wrapper to namespace: $(NAMESPACE)"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - kagent hello-kagent must be deployed in $(NAMESPACE)"
	@echo "  - Namespace must be labeled: kagenti-enabled=true"
	@echo ""
	@echo "→ Labeling namespace..."
	@oc label namespace $(NAMESPACE) kagenti-enabled=true --overwrite
	@echo "  ✓ Namespace labeled"
	@echo ""
	@echo "→ Deploying wrapper resources..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" kagenti/hello-kagent-wrapper.yaml | oc apply -f -
	@echo "  ✓ Wrapper deployed"
	@echo ""
	@echo "→ Patching service selector to use existing kagent pods..."
	@sleep 3
	@oc patch svc hello-kagent-kagenti -n $(NAMESPACE) --type='json' -p='[{"op": "replace", "path": "/spec/selector", "value": {"app": "kagent", "kagent": "hello-kagent"}}]' 2>/dev/null || true
	@echo "  ✓ Service patched"
	@echo ""
	@echo "→ Checking AgentCard..."
	@sleep 5
	@oc get agentcards.agent.kagenti.dev -n $(NAMESPACE) 2>/dev/null || echo "  No AgentCards found (kagenti-operator may not be installed)"
	@echo ""
	@echo "✓ Wrapper deployed!"
	@echo ""
	@echo "The hello-kagent agent should now be discoverable in kagenti-ui"
	@echo "URL: https://$$(oc get route kagenti-ui -n $(NAMESPACE) -o jsonpath='{.status.ingress[0].host}' 2>/dev/null || echo 'kagenti-ui.<cluster>')"

deploy-kagenti-ui:
	@echo ""
	@echo "Deploying kagenti-ui to namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Creating ConfigMap..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" kagenti/ui-configmap.yaml | oc apply -f -
	@echo "  ✓ ConfigMap created"
	@echo ""
	@echo "→ Deploying kagenti-ui..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" kagenti/ui-deployment.yaml | oc apply -f -
	@echo "  ✓ Deployment created"
	@echo ""
	@echo "→ Creating Route..."
	@sed "s/NAMESPACE_PLACEHOLDER/$(NAMESPACE)/g" kagenti/ui-route.yaml | oc apply -f -
	@echo "  ✓ Route created"
	@echo ""
	@echo "→ Waiting for kagenti-ui to be ready..."
	@timeout 120 bash -c 'until oc get pods -n $(NAMESPACE) -l app=kagenti-ui -o jsonpath="{.items[0].status.phase}" 2>/dev/null | grep -q "Running"; do echo "  Waiting for kagenti-ui..."; sleep 5; done' || \
		echo "  ⚠ kagenti-ui not ready yet. Check: oc logs -n $(NAMESPACE) -l app=kagenti-ui"
	@echo ""
	@echo "✓ kagenti-ui deployed!"
	@echo ""
	@echo "Access the UI:"
	@echo "  URL: https://$$(oc get route kagenti-ui -n $(NAMESPACE) -o jsonpath='{.status.ingress[0].host}' 2>/dev/null || echo 'kagenti-ui.<cluster-domain>')"
	@echo ""
	@echo "Or via port-forward:"
	@echo "  oc port-forward -n $(NAMESPACE) svc/kagenti-ui 8501:8501"
	@echo "  open http://localhost:8501"
	@echo ""
	@echo "Note: Authentication is disabled in standalone mode."

clean:
	@echo "Removing deployments from namespace: $(NAMESPACE)"
	@echo ""
	@echo "→ Removing cagent Agent..."
	@oc delete deployment hello-cagent -n $(NAMESPACE) 2>/dev/null || echo "  Deployment not found"
	@oc delete service hello-cagent -n $(NAMESPACE) 2>/dev/null || echo "  Service not found"
	@oc delete buildconfig hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  BuildConfig not found"
	@oc delete imagestream hello-agent -n $(NAMESPACE) 2>/dev/null || echo "  ImageStream not found"
	@echo ""
	@echo "→ Removing MLflow Agent..."
	@oc delete deployment mlflow-agent-helloworld -n $(NAMESPACE) 2>/dev/null || echo "  Deployment not found"
	@oc delete service mlflow-agent-helloworld -n $(NAMESPACE) 2>/dev/null || echo "  Service not found"
	@echo ""
	@echo "→ Removing kagent Agent..."
	@oc delete agent hello-kagent -n $(NAMESPACE) 2>/dev/null || echo "  Agent CRD not found"
	@oc delete modelconfig llama-stack-model -n $(NAMESPACE) 2>/dev/null || echo "  ModelConfig not found"
	@oc delete secret llama-stack-dummy-key -n $(NAMESPACE) 2>/dev/null || echo "  Secret not found"
	@echo ""
	@echo "→ Removing Vector Store Setup..."
	@oc delete job vectorstore-setup -n $(NAMESPACE) 2>/dev/null || echo "  Job not found"
	@oc delete buildconfig vectorstore-setup -n $(NAMESPACE) 2>/dev/null || echo "  BuildConfig not found"
	@oc delete imagestream vectorstore-setup -n $(NAMESPACE) 2>/dev/null || echo "  ImageStream not found"
	@echo ""
	@echo "→ Removing Llama Stack..."
	@oc delete llamastackdistribution llama-stack -n $(NAMESPACE) 2>/dev/null || echo "  LlamaStackDistribution not found"
	@oc delete configmap llama-stack-config -n $(NAMESPACE) 2>/dev/null || echo "  ConfigMap not found"
	@echo ""
	@echo "→ Removing vLLM model..."
	@oc delete inferenceservice qwen3-14b-awq -n $(NAMESPACE) 2>/dev/null || echo "  InferenceService not found"
	@echo ""
	@echo "→ Removing OTEL Collector..."
	@oc delete deployment otel-collector -n $(NAMESPACE) 2>/dev/null || echo "  Deployment not found"
	@oc delete service otel-collector -n $(NAMESPACE) 2>/dev/null || echo "  Service not found"
	@oc delete configmap otel-collector-config -n $(NAMESPACE) 2>/dev/null || echo "  ConfigMap not found"
	@echo ""
	@echo "→ Removing kagenti-ui..."
	@oc delete route kagenti-ui -n $(NAMESPACE) 2>/dev/null || echo "  Route not found"
	@oc delete deployment kagenti-ui -n $(NAMESPACE) 2>/dev/null || echo "  Deployment not found"
	@oc delete service kagenti-ui -n $(NAMESPACE) 2>/dev/null || echo "  Service not found"
	@oc delete configmap kagenti-ui-config -n $(NAMESPACE) 2>/dev/null || echo "  ConfigMap not found"
	@oc delete configmap environments -n $(NAMESPACE) 2>/dev/null || echo "  Environments ConfigMap not found"
	@oc delete serviceaccount kagenti-ui-service-account -n $(NAMESPACE) 2>/dev/null || echo "  ServiceAccount not found"
	@oc delete clusterrolebinding kagenti-ui-binding 2>/dev/null || echo "  ClusterRoleBinding not found"
	@oc delete clusterrole kagenti-ui-role 2>/dev/null || echo "  ClusterRole not found"
	@echo ""
	@echo "→ Removing kagenti wrapper..."
	@oc delete agents.agent.kagenti.dev hello-kagent -n $(NAMESPACE) 2>/dev/null || echo "  Agent wrapper not found"
	@oc delete service hello-kagent-kagenti -n $(NAMESPACE) 2>/dev/null || echo "  Service alias not found"
	@echo ""
	@echo "→ Removing MLflow stack..."
	@oc delete deployment mlflow -n $(NAMESPACE) 2>/dev/null || echo "  MLflow deployment not found"
	@oc delete deployment mlflow-minio -n $(NAMESPACE) 2>/dev/null || echo "  MinIO deployment not found"
	@oc delete deployment mlflow-postgres -n $(NAMESPACE) 2>/dev/null || echo "  PostgreSQL deployment not found"
	@oc delete service mlflow -n $(NAMESPACE) 2>/dev/null || echo "  MLflow service not found"
	@oc delete service mlflow-minio -n $(NAMESPACE) 2>/dev/null || echo "  MinIO service not found"
	@oc delete service mlflow-postgres -n $(NAMESPACE) 2>/dev/null || echo "  PostgreSQL service not found"
	@oc delete pvc mlflow-minio-pvc -n $(NAMESPACE) 2>/dev/null || echo "  MinIO PVC not found"
	@oc delete pvc mlflow-postgres-pvc -n $(NAMESPACE) 2>/dev/null || echo "  PostgreSQL PVC not found"
	@oc delete secret mlflow-minio-secret -n $(NAMESPACE) 2>/dev/null || echo "  MinIO secret not found"
	@oc delete secret mlflow-postgres-secret -n $(NAMESPACE) 2>/dev/null || echo "  PostgreSQL secret not found"
	@echo ""
	@echo "✓ Cleanup complete"
	@echo ""
	@echo "Note: Namespace '$(NAMESPACE)' was not deleted. To delete it:"
	@echo "  oc delete namespace $(NAMESPACE)"

