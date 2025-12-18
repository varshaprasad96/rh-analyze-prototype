#!/usr/bin/env python3
"""
Example script showing how to use KagentMLflowLogger with multiple questions.
"""

from kagent_mlflow_logger import KagentMLflowLogger
import time

# Initialize logger with MinIO/S3 configuration
logger = KagentMLflowLogger(
    mlflow_tracking_uri="http://localhost:5000",
    a2a_url="http://localhost:8083/api/a2a/kagent/rh-analyze-simple/",
    experiment_name="rh-analyze-mvp",
    s3_endpoint_url="http://localhost:9000",  # MinIO endpoint
    aws_access_key_id="minio",                  # MinIO access key
    aws_secret_access_key="miniopass123"       # MinIO secret key
)

# List of questions to ask
questions = [
    "In one sentence, what is OpenShift?",
    "What are the main components of Kubernetes?",
    "Explain the difference between a Pod and a Container in Kubernetes.",
]

print("Sending multiple questions to Kagent and logging to MLflow...\n")

for i, question in enumerate(questions, 1):
    print(f"\n[{i}/{len(questions)}] Question: {question}")
    
    try:
        result = logger.send_question(
            question,
            run_name=f"example_run_{i}_{int(time.time())}"
        )
        
        print(f"  Answer: {result['answer']}")
        print(f"  Latency: {result['latency_ms']} ms")
        print(f"  Run ID: {result['run_id']}")
        
        # Small delay between requests
        if i < len(questions):
            time.sleep(1)
            
    except Exception as e:
        print(f"  Error: {e}")
        continue

print("\n\nAll questions logged to MLflow!")
print("View results at: http://localhost:5000")

