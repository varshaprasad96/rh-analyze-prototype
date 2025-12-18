# Example Script Results Documentation

This document explains the results from running `example.py`, which demonstrates how to send multiple questions to Kagent and log the results to MLflow.

## Overview

The `example.py` script sends three predefined questions to the Kagent A2A endpoint and logs each interaction to MLflow. Each question creates a separate MLflow run with metrics, tags, and artifacts.

## Example Run Results

### Question 1: "In one sentence, what is OpenShift?"

**Run ID:** `51ed67c662ae4b0589ce32257908955b`  
**Latency:** 2,113 ms (2.1 seconds)

**Answer:**
> OpenShift is a comprehensive container orchestration platform that enables organizations to build, deploy, and manage containerized applications in their infrastructure.

**Analysis:**
- Fast response time (~2 seconds)
- Concise, accurate answer
- Good for simple, factual questions

---

### Question 2: "What are the main components of Kubernetes?"

**Run ID:** `d95cb9538ba64db2a71bc36948dbfed5`  
**Latency:** 10,347 ms (10.3 seconds)

**Answer:**
The main components of Kubernetes are:

1. **Pods**: The smallest deployment unit in Kubernetes, a pod represents an instance of a container.
2. **ReplicaSets** (RS): Ensures a specified number of replicas (i.e., copies) of the same type of replica set exist across all available devices.
3. **Deployments** (Deployment): Manages the rollout of new versions of an application in Kubernetes, while ensuring minimal disruption to users.
4. **Services**: Provides a network identity and load balancing for accessing the Pods it schedules, helping other Pods access the Service.
5. **Persistent Volumes** (PV) and **Persistent Volume Claims** (PVC): Stores data that needs to be preserved across pod restarts or when the cluster is unavailable.

**Analysis:**
- Longer response time (~10 seconds) due to more complex question requiring detailed explanation
- Structured answer with numbered list
- Covers main Kubernetes components comprehensively
- Good for questions requiring detailed explanations

---

### Question 3: "Explain the difference between a Pod and a Container in Kubernetes."

**Run ID:** `c70c38548d724a80940a468aa4061f91`  
**Latency:** 21,305 ms (21.3 seconds)

**Answer:**
> Hello! For MVP Red Hat Analyze (MVP), I'm ready to help.
>
> In Kubernetes, Pods and Containers are two related but distinct concepts:
>
> **Pods:** A Pod is the basic execution unit in Kubernetes. It represents a logical group of one or more containers running on a single host machine. A Pod can consist of one or more Containers, and it provides the minimum resources needed for those Containers to run.
>
> Think of a Pod as a "self-sufficient" entity that contains the necessary infrastructure (CPU, Memory) to execute its Containers.
>
> **Containers:** A Container is an individual process that runs within a Pod. It represents a lightweight executable package that contains code and settings necessary for runtime execution.
>
> [Additional detailed explanation follows...]

**Analysis:**
- Longest response time (~21 seconds) - most complex question
- Includes conversational greeting (agent personality)
- Very detailed explanation with examples
- Good for conceptual questions requiring in-depth explanations
- Shows the agent's ability to provide educational content

---

## Performance Summary

| Question | Complexity | Latency | Answer Quality |
|----------|-----------|---------|----------------|
| Simple definition | Low | 2.1s | ✅ Concise |
| Component list | Medium | 10.3s | ✅ Structured |
| Conceptual explanation | High | 21.3s | ✅ Detailed |

## What Gets Logged to MLflow

For each run, the following information is logged:

### Tags
- `agent`: "rh-analyze-simple"
- `a2a_url`: The A2A endpoint URL
- `kagent_task_id`: Task ID from Kagent (if available)
- `kagent_context_id`: Context ID from Kagent (if available)

### Metrics
- `latency_ms`: Request latency in milliseconds
- Additional metrics from `kagent_usage_metadata` (e.g., token counts, model usage)

### Artifacts
- `question.txt`: The original question asked
- `answer.txt`: The extracted answer text
- `a2a_response.json`: Complete JSON response from Kagent (includes full conversation history, metadata, etc.)

## Viewing Results in MLflow UI

1. **Open MLflow UI:**
   ```bash
   # If not already running, start MLflow UI
   mlflow ui --backend-store-uri http://localhost:5000
   ```

2. **Access the UI:**
   - Navigate to: `http://localhost:5000`
   - Select experiment: `rh-analyze-mvp`
   - View individual runs by clicking on run names

3. **Compare Runs:**
   - Use the MLflow UI to compare metrics across runs
   - Filter by tags (e.g., agent name)
   - Download artifacts for detailed analysis

## Key Observations

1. **Latency Scales with Complexity:**
   - Simple questions: ~2 seconds
   - Medium complexity: ~10 seconds
   - Complex explanations: ~20+ seconds

2. **Answer Quality:**
   - All answers are relevant and accurate
   - Agent adapts response style to question complexity
   - Structured responses for list-type questions
   - Detailed explanations for conceptual questions

3. **Consistent Logging:**
   - All runs successfully logged to MLflow
   - Artifacts properly stored in MinIO
   - Metrics and tags correctly captured

## Use Cases

This example demonstrates:

- **Performance Monitoring:** Track latency and usage metrics over time
- **Quality Assurance:** Review answers and compare across different questions
- **Cost Analysis:** Monitor token usage and API costs
- **A/B Testing:** Compare different agents or configurations
- **Audit Trail:** Maintain complete records of all interactions

## Next Steps

- Modify `example.py` to test different question types
- Add more questions to the list
- Experiment with different agents by changing the `a2a_url`
- Analyze trends in MLflow UI over multiple runs
- Export data for further analysis

