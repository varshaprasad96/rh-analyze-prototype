#!/bin/bash
# Demo Script for A2A Agent Orchestration
# This script demonstrates kagent agents with A2A protocol and MLflow tracing
# Suitable for screen recording and presentation

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    sleep 2
}

# Function to print explanation
print_explanation() {
    echo -e "${YELLOW}$1${NC}"
    echo ""
    sleep 3
}

# Function to wait for user
wait_for_demo() {
    echo -e "${GREEN}Press Enter to continue...${NC}"
    read
}

clear

print_section "A2A Agent Orchestration Demo"
echo "This demo shows:"
echo "1. Llamastack agent deployed via kagent"
echo "2. Default kagent agent (rh-analyze-simple)"
echo "3. Orchestrator agent that coordinates multiple agents"
echo "4. A2A protocol communication between agents"
echo "5. MLflow tracing of all interactions"
echo ""
wait_for_demo

# ============================================
# Part 1: Llamastack Agent
# ============================================
print_section "Part 1: Llamastack Agent with Ollama Model"

print_explanation "I have deployed a Llamastack agent using kagent.
This agent uses Llamastack (LLS) as the backend, which connects to an Ollama model.
The agent is deployed as a Kubernetes resource using kagent's Agent CRD."

echo "Checking the agent status..."
kubectl get agents.kagent.dev llamastack-a2a-agent -n rh-analyze

echo ""
print_explanation "The agent is running and has been port-forwarded to localhost:8080"

echo "Getting the agent's capabilities (A2A discovery)..."
curl -s http://localhost:8080/.well-known/agent.json | python3 -m json.tool | head -25

echo ""
print_explanation "Now let's send a request to this individual agent endpoint..."

echo "Sending question: 'What is Llamastack?'"
echo ""
RESPONSE=$(curl -s -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-demo-1",
        "role": "user",
        "parts": [{"kind": "text", "text": "What is Llamastack?"}]
      }
    }
  }')

echo "$RESPONSE" | python3 -m json.tool | head -30

# Extract and show answer
ANSWER=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); artifacts=data.get('result', {}).get('artifacts', []); print(artifacts[0].get('parts', [{}])[0].get('text', 'No answer') if artifacts else 'No answer found')" 2>/dev/null)
echo ""
echo -e "${GREEN}Agent Response:${NC}"
echo "$ANSWER"
echo ""

wait_for_demo

# ============================================
# Part 2: Default Kagent Agent
# ============================================
print_section "Part 2: Default Kagent Agent (rh-analyze-simple)"

print_explanation "Kagent comes with several default agents pre-configured.
One of them is 'rh-analyze-simple' which is a simple Q&A agent.
This agent was created using kagent's declarative YAML configuration."

echo "Checking the default agent..."
kubectl get agents.kagent.dev rh-analyze-simple -n kagent

echo ""
print_explanation "This agent is also port-forwarded to localhost:8081"

echo "Getting agent capabilities..."
curl -s http://localhost:8081/.well-known/agent.json | python3 -m json.tool | head -20

echo ""
print_explanation "Let's test this default agent..."

echo "Sending question: 'What is kagent?'"
echo ""
RESPONSE2=$(curl -s -X POST http://localhost:8081/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-demo-2",
        "role": "user",
        "parts": [{"kind": "text", "text": "What is kagent?"}]
      }
    }
  }')

echo "$RESPONSE2" | python3 -m json.tool | head -30

ANSWER2=$(echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); artifacts=data.get('result', {}).get('artifacts', []); print(artifacts[0].get('parts', [{}])[0].get('text', 'No answer') if artifacts else 'No answer found')" 2>/dev/null)
echo ""
echo -e "${GREEN}Agent Response:${NC}"
echo "$ANSWER2"
echo ""

wait_for_demo

# ============================================
# Part 3: Orchestrator Agent
# ============================================
print_section "Part 3: Orchestrator Agent"

print_explanation "We have deployed an orchestrator agent that coordinates tasks across multiple specialized agents.
The orchestrator can analyze questions and delegate to the appropriate agent(s) via A2A protocol."

echo "Checking orchestrator agent..."
kubectl get agents.kagent.dev orchestrator-agent -n rh-analyze

echo ""
print_explanation "The orchestrator is port-forwarded to localhost:8082"

echo "Getting orchestrator capabilities..."
curl -s http://localhost:8082/.well-known/agent.json | python3 -m json.tool | head -20

wait_for_demo

# ============================================
# Part 4: A2A Communication Demo
# ============================================
print_section "Part 4: Agent-to-Agent (A2A) Communication"

print_explanation "Now we'll demonstrate A2A protocol communication.
The orchestrator will call both agents and combine their responses.
All interactions will be logged to MLflow with full traces."

echo ""
echo "Running orchestrator script that:"
echo "  1. Calls Agent 1 (llamastack-a2a-agent) via A2A"
echo "  2. Calls Agent 2 (rh-analyze-simple) via A2A"
echo "  3. Logs all interactions to MLflow with traces"
echo "  4. Combines responses"
echo ""

wait_for_demo

# Run the orchestrator logger
cd "$(dirname "$0")"
source $(conda info --base)/etc/profile.d/conda.sh 2>/dev/null || true
conda activate stack-client 2>/dev/null || true

export MLFLOW_TRACKING_URI="http://localhost:5000"
export ORCHESTRATOR_URL="http://localhost:8082"
export AGENT1_URL="http://localhost:8080"
export AGENT2_URL="http://localhost:8081"
export MLFLOW_S3_ENDPOINT_URL="http://localhost:9000"
export AWS_ACCESS_KEY_ID="minio"
export AWS_SECRET_ACCESS_KEY="miniopass123"

QUESTION="What is kagent and how does it work with Llamastack?"

echo -e "${GREEN}Question: $QUESTION${NC}"
echo ""

python3 orchestrator_mlflow_logger.py "$QUESTION"

echo ""
print_section "Demo Complete!"

echo -e "${GREEN}Summary:${NC}"
echo "✅ Llamastack agent deployed via kagent"
echo "✅ Default kagent agent (rh-analyze-simple)"
echo "✅ Orchestrator agent coordinating multiple agents"
echo "✅ A2A protocol communication working"
echo "✅ All interactions logged to MLflow with traces"
echo ""
echo "View traces in MLflow UI: http://localhost:5000"
echo ""

