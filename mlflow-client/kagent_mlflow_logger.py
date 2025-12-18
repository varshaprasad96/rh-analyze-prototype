#!/usr/bin/env python3
"""
Kagent MLflow Logger

This script sends questions to a Kagent A2A endpoint and logs the results to MLflow.
"""

import json
import os
import sys
import time
from typing import Dict, Any, Optional

import mlflow
import requests

# Configure boto3 for MinIO/S3 compatibility
try:
    import boto3
    from botocore.client import Config
except ImportError:
    boto3 = None


class KagentMLflowLogger:
    """Logger for Kagent interactions to MLflow."""
    
    def __init__(
        self,
        mlflow_tracking_uri: str = "http://localhost:5000",
        a2a_url: str = "http://localhost:8083/api/a2a/kagent/rh-analyze-simple/",
        experiment_name: str = "rh-analyze-mvp",
        s3_endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize the logger.
        
        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            a2a_url: Kagent A2A endpoint URL
            experiment_name: MLflow experiment name
            s3_endpoint_url: S3/MinIO endpoint URL (e.g., http://localhost:9000)
            aws_access_key_id: AWS/MinIO access key ID
            aws_secret_access_key: AWS/MinIO secret access key
        """
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.a2a_url = a2a_url
        self.experiment_name = experiment_name
        
        # Configure S3/MinIO credentials if provided
        if s3_endpoint_url or aws_access_key_id or aws_secret_access_key:
            self._configure_s3_credentials(
                s3_endpoint_url or os.getenv("MLFLOW_S3_ENDPOINT_URL"),
                aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
            )
        
        # Set up MLflow
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment(experiment_name)
    
    def _configure_s3_credentials(
        self,
        endpoint_url: Optional[str],
        access_key_id: Optional[str],
        secret_access_key: Optional[str]
    ):
        """Configure S3/MinIO credentials for MLflow artifact storage."""
        if endpoint_url:
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = endpoint_url
        if access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = access_key_id
        if secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = secret_access_key
    
    def extract_answer(self, response: Dict[str, Any]) -> str:
        """
        Extract the answer from the Kagent response.
        
        Args:
            response: JSON response from Kagent
            
        Returns:
            Extracted answer text
        """
        answer = ""
        
        # Try to get answer from artifacts
        artifacts = response.get("result", {}).get("artifacts", []) or []
        if artifacts and artifacts[0].get("parts"):
            answer = artifacts[0]["parts"][0].get("text", "")
        
        # If no answer in artifacts, try history
        if not answer:
            history = response.get("result", {}).get("history", []) or []
            for message in reversed(history):
                if message.get("role") == "agent" and message.get("parts"):
                    answer = message["parts"][0].get("text", "")
                    break
        
        return answer or "<empty>"
    
    def send_question(
        self,
        question: str,
        run_name: Optional[str] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Send a question to Kagent and log results to MLflow.
        
        Args:
            question: Question to ask the agent
            run_name: Optional name for the MLflow run
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with answer, run_id, and response
        """
        # Prepare payload
        payload = {
            "jsonrpc": "2.0",
            "id": "local-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": question}]
                }
            }
        }
        
        # Send request and measure latency
        t0 = time.time()
        try:
            r = requests.post(self.a2a_url, json=payload, timeout=timeout)
            r.raise_for_status()
            resp = r.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending request: {e}", file=sys.stderr)
            raise
        
        latency_ms = int((time.time() - t0) * 1000)
        
        # Extract information
        answer = self.extract_answer(resp)
        usage = resp.get("result", {}).get("metadata", {}).get("kagent_usage_metadata", {}) or {}
        task_id = resp.get("result", {}).get("id", "")
        context_id = resp.get("result", {}).get("contextId", "")
        
        # Generate run name if not provided
        if not run_name:
            timestamp = int(time.time())
            run_name = f"kagent_{timestamp}"
        
        # Log to MLflow
        with mlflow.start_run(run_name=run_name) as run:
            # Tags
            mlflow.set_tag("agent", "rh-analyze-simple")
            mlflow.set_tag("a2a_url", self.a2a_url)
            if task_id:
                mlflow.set_tag("kagent_task_id", task_id)
            if context_id:
                mlflow.set_tag("kagent_context_id", context_id)
            
            # Metrics
            mlflow.log_metric("latency_ms", latency_ms)
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(key, value)
            
            # Artifacts
            mlflow.log_text(question, "question.txt")
            mlflow.log_text(answer, "answer.txt")
            mlflow.log_text(json.dumps(resp, indent=2), "a2a_response.json")
        
        return {
            "answer": answer,
            "run_id": run.info.run_id,
            "response": resp,
            "latency_ms": latency_ms
        }


def main():
    """Main entry point."""
    # Get configuration from environment variables or use defaults
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    a2a_url = os.getenv("A2A_URL", "http://localhost:8083/api/a2a/kagent/rh-analyze-simple/")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT", "rh-analyze-mvp")
    
    # S3/MinIO configuration (for artifact storage)
    s3_endpoint_url = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "minio")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "miniopass123")
    
    # Get question from command line or use default
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "In one sentence, what is OpenShift?"
    
    # Create logger and send question
    logger = KagentMLflowLogger(
        mlflow_tracking_uri=mlflow_uri,
        a2a_url=a2a_url,
        experiment_name=experiment_name,
        s3_endpoint_url=s3_endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    
    print(f"Sending question to Kagent: {question}")
    print(f"MLflow URI: {mlflow_uri}")
    print(f"A2A URL: {a2a_url}")
    print()
    
    try:
        result = logger.send_question(question)
        print(f"Answer: {result['answer']}")
        print(f"Latency: {result['latency_ms']} ms")
        print(f"Logged run to MLflow: {result['run_id']}")
        print(f"MLflow UI: {mlflow_uri}/#/experiments/0/runs/{result['run_id']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

