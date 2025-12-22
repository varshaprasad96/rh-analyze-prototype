#!/usr/bin/env python3
"""
Log Llamastack Agent Wrapper Directly to MLflow

This script instantiates a LlamastackAgentWrapper directly (similar to LangGraph)
and logs it using set_model(), rather than using file-based logging.
"""

import os
import sys

import mlflow
from mlflow.models import set_model
from llamastack_agent_wrapper_direct import LlamastackAgentWrapper


def main():
    """Main entry point for logging the agent."""
    # Get configuration from environment variables or use defaults
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    llamastack_base_url = os.getenv(
        "LLAMASTACK_BASE_URL", 
        "http://localhost:8321"
    )
    agent_id = os.getenv("LLAMASTACK_AGENT_ID", "default-agent")
    api_key = os.getenv("LLAMASTACK_API_KEY", "fake")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT", "llamastack-agent-wrapper-direct")
    model_name = os.getenv("MLFLOW_MODEL_NAME", "llamastack-agent-wrapper-direct")
    
    # S3/MinIO configuration (for artifact storage)
    s3_endpoint_url = os.getenv("MLFLOW_S3_ENDPOINT_URL")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # Configure S3/MinIO credentials if provided
    if s3_endpoint_url:
        os.environ["MLFLOW_S3_ENDPOINT_URL"] = s3_endpoint_url
    if aws_access_key_id:
        os.environ["AWS_ACCESS_KEY_ID"] = aws_access_key_id
    if aws_secret_access_key:
        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key
    
    # Set up MLflow
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment(experiment_name)
    
    print(f"MLflow URI: {mlflow_uri}")
    print(f"Llamastack Base URL: {llamastack_base_url}")
    print(f"Agent ID: {agent_id}")
    print(f"Experiment: {experiment_name}")
    print(f"Model Name: {model_name}")
    print()
    
    # Log the agent using file-based approach with set_model() (like LangGraph)
    print("Logging Llamastack Agent Wrapper (direct instantiation pattern)...")
    with mlflow.start_run():
        # Set environment variables for the agent file to use
        os.environ["LLAMASTACK_BASE_URL"] = llamastack_base_url
        os.environ["LLAMASTACK_AGENT_ID"] = agent_id
        os.environ["LLAMASTACK_API_KEY"] = api_key
        
        # Log using the file - the file has set_model() called in it
        # This is the LangGraph pattern: define agent in file, instantiate and set_model() in file
        agent_file = "llamastack_agent_wrapper_direct.py"
        
        # Try to register the model, but fall back to unregistered if registration fails
        try:
            logged_agent_info = mlflow.pyfunc.log_model(
                python_model=agent_file,
                artifact_path="agent",
                registered_model_name=model_name,  # Register with name for easier access
            )
            print(f"✓ Model registered as: {model_name}")
            print(f"  Serve with: mlflow models serve -m models:/{model_name}/latest -p 8080")
        except Exception as e:
            # If registration fails, log without registration
            print(f"⚠️  Model registration failed: {e}")
            print(f"   Logging model without registration (using run ID instead)...")
            logged_agent_info = mlflow.pyfunc.log_model(
                python_model=agent_file,
                artifact_path="agent",
                registered_model_name=None,  # Don't register
            )
            run_id = mlflow.active_run().info.run_id
            print(f"✓ Model logged (unregistered)")
            print(f"  Serve with: mlflow models serve -m runs:/{run_id}/agent -p 8080")
        
        # Log metadata
        mlflow.set_tag("agent_type", "llamastack-agent-wrapper-direct")
        mlflow.set_tag("wrapper_type", "direct-instantiation")
        mlflow.set_tag("llamastack_base_url", llamastack_base_url)
        mlflow.set_tag("agent_id", agent_id)
        
        print(f"✓ Agent wrapper logged successfully!")
        print(f"  Model URI: {logged_agent_info.model_uri}")
        print(f"  Run ID: {mlflow.active_run().info.run_id}")
        print()
        print("To serve the agent locally:")
        print(f"  mlflow models serve -m {logged_agent_info.model_uri} -p 5000")
        print()
        print("Or serve using the registered model:")
        print(f"  mlflow models serve -m models:/{model_name}/latest -p 5000")
        print()
        print(f"View in MLflow UI: {mlflow_uri}/#/experiments/0/runs/{mlflow.active_run().info.run_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

