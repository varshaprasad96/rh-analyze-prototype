#!/usr/bin/env python3
"""
Orchestrator Agent MLflow Logger

This script demonstrates an orchestrator agent that:
1. Receives questions
2. Delegates to specialized agents via A2A protocol
3. Logs all interactions to MLflow with traces
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, Optional, List

import mlflow
try:
    from mlflow.trace import trace
except ImportError:
    # Fallback if trace decorator not available
    def trace(func):
        return func

# Configure boto3 for MinIO/S3 compatibility
try:
    import boto3
    from botocore.client import Config
except ImportError:
    boto3 = None


class OrchestratorMLflowLogger:
    """Orchestrator that delegates to agents and logs to MLflow."""
    
    def __init__(
        self,
        mlflow_tracking_uri: str = "http://localhost:5000",
        orchestrator_url: str = "http://localhost:8082",
        agent1_url: str = "http://localhost:8080",  # llamastack-a2a-agent
        agent2_url: str = "http://localhost:8081",  # rh-analyze-simple
        experiment_name: str = "orchestrator-agent",
        s3_endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize the orchestrator logger.
        
        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            orchestrator_url: Orchestrator agent A2A endpoint URL
            agent1_url: Agent 1 A2A endpoint URL
            agent2_url: Agent 2 A2A endpoint URL
            experiment_name: MLflow experiment name
            s3_endpoint_url: S3/MinIO endpoint URL
            aws_access_key_id: AWS/MinIO access key ID
            aws_secret_access_key: AWS/MinIO secret access key
        """
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.orchestrator_url = orchestrator_url
        self.agent1_url = agent1_url
        self.agent2_url = agent2_url
        self.experiment_name = experiment_name
        
        # Configure MLflow
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment(experiment_name)
        
        # Configure S3/MinIO if provided
        if s3_endpoint_url:
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = s3_endpoint_url
        if aws_access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key_id
        if aws_secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
    
    @trace
    def call_agent_via_a2a(self, agent_url: str, message: str, agent_name: str) -> Dict[str, Any]:
        """Call an agent via A2A protocol with MLflow tracing."""
        payload = {
            "jsonrpc": "2.0",
            "id": f"a2a-{int(time.time())}",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": f"msg-{int(time.time())}",
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}]
                }
            }
        }
        
        t0 = time.time()
        try:
            response = requests.post(agent_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            latency_ms = int((time.time() - t0) * 1000)
            
            # Extract answer
            answer = self._extract_answer(result)
            
            return {
                "success": True,
                "agent": agent_name,
                "answer": answer,
                "latency_ms": latency_ms,
                "full_response": result
            }
        except Exception as e:
            return {
                "success": False,
                "agent": agent_name,
                "error": str(e),
                "latency_ms": int((time.time() - t0) * 1000)
            }
    
    def _extract_answer(self, response: Dict[str, Any]) -> str:
        """Extract answer from A2A response."""
        result = response.get("result", {})
        
        # Try artifacts first
        artifacts = result.get("artifacts", [])
        if artifacts:
            parts = artifacts[0].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        
        # Fall back to history
        history = result.get("history", [])
        for msg in reversed(history):
            if msg.get("role") == "agent":
                parts = msg.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
        
        return "<no answer found>"
    
    @trace
    def orchestrate_question(self, question: str, run_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Orchestrate a question by delegating to appropriate agents.
        
        This method:
        1. Analyzes the question
        2. Decides which agent(s) to call
        3. Calls agents via A2A
        4. Logs everything to MLflow
        """
        if not run_name:
            run_name = f"orchestrator_{int(time.time())}"
        
        with mlflow.start_run(run_name=run_name) as run:
            # Log input question
            mlflow.log_param("question", question)
            mlflow.log_param("orchestrator_url", self.orchestrator_url)
            
            # Determine which agent to call based on question
            question_lower = question.lower()
            agents_to_call = []
            
            if any(word in question_lower for word in ["kagent", "kubernetes", "openshift", "deployment"]):
                agents_to_call.append(("rh-analyze-simple", self.agent2_url))
            
            if any(word in question_lower for word in ["llamastack", "lls", "mlflow", "model"]):
                agents_to_call.append(("llamastack-a2a-agent", self.agent1_url))
            
            # If no specific match, call both agents
            if not agents_to_call:
                agents_to_call = [
                    ("llamastack-a2a-agent", self.agent1_url),
                    ("rh-analyze-simple", self.agent2_url)
                ]
            
            mlflow.log_param("agents_called", [name for name, _ in agents_to_call])
            
            # Call agents and collect responses
            all_responses = []
            for agent_name, agent_url in agents_to_call:
                mlflow.log_param(f"agent_{agent_name}_url", agent_url)
                
                response = self.call_agent_via_a2a(agent_url, question, agent_name)
                all_responses.append(response)
                
                # Log agent response
                if response["success"]:
                    mlflow.log_metric(f"{agent_name}_latency_ms", response["latency_ms"])
                    mlflow.log_text(
                        response["answer"],
                        f"{agent_name}_response.txt"
                    )
                    mlflow.log_dict(
                        response["full_response"],
                        f"{agent_name}_full_response.json"
                    )
                else:
                    mlflow.log_param(f"{agent_name}_error", response.get("error", "unknown"))
            
            # Combine responses
            combined_answer = "\n\n".join([
                f"**{r['agent']}:** {r.get('answer', r.get('error', 'No response'))}"
                for r in all_responses
            ])
            
            # Log combined result
            mlflow.log_text(combined_answer, "combined_response.txt")
            mlflow.log_dict({
                "question": question,
                "agents_called": [r["agent"] for r in all_responses],
                "responses": all_responses
            }, "orchestration_result.json")
            
            # Calculate total latency
            total_latency = sum(r.get("latency_ms", 0) for r in all_responses)
            mlflow.log_metric("total_latency_ms", total_latency)
            
            return {
                "run_id": run.info.run_id,
                "question": question,
                "agents_called": [r["agent"] for r in all_responses],
                "combined_answer": combined_answer,
                "responses": all_responses,
                "total_latency_ms": total_latency
            }


def main():
    """Main entry point."""
    # Get configuration from environment variables
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://localhost:8082")
    agent1_url = os.getenv("AGENT1_URL", "http://localhost:8080")
    agent2_url = os.getenv("AGENT2_URL", "http://localhost:8081")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT", "orchestrator-agent")
    
    # S3/MinIO configuration
    s3_endpoint_url = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "minio")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "miniopass123")
    
    # Get question from command line or use default
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "What is kagent and how does it work with Llamastack?"
    
    # Create orchestrator logger
    orchestrator = OrchestratorMLflowLogger(
        mlflow_tracking_uri=mlflow_uri,
        orchestrator_url=orchestrator_url,
        agent1_url=agent1_url,
        agent2_url=agent2_url,
        experiment_name=experiment_name,
        s3_endpoint_url=s3_endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    
    print(f"Orchestrator Agent MLflow Logger")
    print(f"MLflow URI: {mlflow_uri}")
    print(f"Orchestrator URL: {orchestrator_url}")
    print(f"Agent 1 (llamastack-a2a-agent): {agent1_url}")
    print(f"Agent 2 (rh-analyze-simple): {agent2_url}")
    print(f"Question: {question}")
    print()
    
    try:
        result = orchestrator.orchestrate_question(question)
        
        print("✅ Orchestration complete!")
        print(f"Run ID: {result['run_id']}")
        print(f"Agents called: {', '.join(result['agents_called'])}")
        print(f"Total latency: {result['total_latency_ms']} ms")
        print()
        print("Combined Answer:")
        print("-" * 70)
        print(result['combined_answer'])
        print("-" * 70)
        print()
        print(f"View in MLflow UI: {mlflow_uri}/#/experiments/0/runs/{result['run_id']}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

