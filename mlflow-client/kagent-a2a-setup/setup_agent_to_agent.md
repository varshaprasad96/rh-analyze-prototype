# Setting Up Agent-to-Agent Communication

## Overview

This guide shows how to set up communication between two kagent agents using A2A (Agent-to-Agent) protocol.

**Agents:**
- Agent 1: `llamastack-a2a-agent` (namespace: `rh-analyze`)
- Agent 2: `rh-analyze-simple` (namespace: `kagent`) - or any other agent

## Step 1: Port-Forward Both Agents

You need to port-forward both agents to access them locally:

```bash
# Terminal 1: Port-forward Agent 1 (llamastack-a2a-agent)
kubectl port-forward svc/llamastack-a2a-agent 8080:8080 -n rh-analyze

# Terminal 2: Port-forward Agent 2 (rh-analyze-simple)
kubectl port-forward svc/rh-analyze-simple 8081:8080 -n kagent
```

## Step 2: Discover Agent Capabilities

### Get Agent 1 Card
```bash
curl http://localhost:8080/.well-known/agent.json | jq
```

### Get Agent 2 Card
```bash
curl http://localhost:8081/.well-known/agent.json | jq
```

## Step 3: Test Agent-to-Agent Communication

### Option A: Using Python Script

```bash
export AGENT1_URL="http://localhost:8080"
export AGENT2_URL="http://localhost:8081"
python test_agent_to_agent.py
```

### Option B: Using curl

**Agent 1 asks Agent 2:**
```bash
curl -X POST http://localhost:8081/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is kagent?", "skill": "answer"}'
```

**Agent 2 asks Agent 1:**
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Llamastack?", "skill": "answer"}'
```

## Step 4: Within Cluster Communication

If both agents are in the cluster, you can call them directly:

**From Agent 1 pod, call Agent 2:**
```bash
kubectl exec -n rh-analyze deployment/llamastack-a2a-agent -- \
  curl -X POST http://rh-analyze-simple.kagent.svc.cluster.local:8080/ \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello from Agent 1!", "skill": "answer"}'
```

**From Agent 2 pod, call Agent 1:**
```bash
kubectl exec -n kagent deployment/rh-analyze-simple -- \
  curl -X POST http://llamastack-a2a-agent.rh-analyze.svc.cluster.local:8080/ \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello from Agent 2!", "skill": "answer"}'
```

## Step 5: Create an Orchestrator Agent

You can create an orchestrator agent that coordinates between multiple agents:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: orchestrator-agent
  namespace: rh-analyze
spec:
  description: "Orchestrator that delegates tasks to other agents"
  type: Declarative
  declarative:
    modelConfig: lls-openai
    systemMessage: |
      You are an orchestrator agent. When you receive a question:
      1. If it's about Kubernetes agents or kagent, delegate to rh-analyze-simple agent
      2. If it's about Llamastack or MLflow, handle it yourself
      3. You can call other agents via A2A protocol
    a2aConfig:
      skills:
        - id: orchestrate
          name: orchestrate
          description: Orchestrate tasks across multiple agents
```

## Example: Multi-Agent Workflow

```
User Question: "What is kagent and how does it work with Llamastack?"

Orchestrator Agent:
  1. Receives question
  2. Analyzes: needs info about both kagent and Llamastack
  3. Calls rh-analyze-simple: "What is kagent?"
  4. Calls llamastack-a2a-agent: "What is Llamastack?"
  5. Combines responses and returns to user
```

## Troubleshooting

### Agents can't reach each other

Check service DNS:
```bash
# From Agent 1 pod
kubectl exec -n rh-analyze deployment/llamastack-a2a-agent -- \
  nslookup rh-analyze-simple.kagent.svc.cluster.local

# From Agent 2 pod
kubectl exec -n kagent deployment/rh-analyze-simple -- \
  nslookup llamastack-a2a-agent.rh-analyze.svc.cluster.local
```

### Check agent services

```bash
# Agent 1 service
kubectl get svc llamastack-a2a-agent -n rh-analyze

# Agent 2 service
kubectl get svc rh-analyze-simple -n kagent
```

