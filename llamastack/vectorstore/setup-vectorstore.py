#!/usr/bin/env python3
"""
Setup vector store in Llama Stack with documentation from Varsha's repository.
"""
import os
import sys
import time
import requests
from typing import List, Dict

# Configuration
LLAMA_STACK_URL = os.environ.get("LLAMA_STACK_URL", "http://llama-stack-service:8321")
GITHUB_REPO_URL = "https://api.github.com/repos/varshaprasad96/rh-analyze-prototype/contents/docs"
VECTOR_STORE_NAME = "docs-vectorstore"
EMBEDDING_MODEL = "granite-embedding-125m"

# Documentation files to fetch
DOCS_FILES = [
    "architecture-proposal.md",
    "cagent.md",
    "kagent.md",
    "kagenti.md",
    "llama-stack.md",
    "mlflow.md"
]


def fetch_github_files() -> List[Dict[str, str]]:
    """Fetch markdown files from GitHub repository."""
    print(f"→ Fetching file list from GitHub...")
    
    response = requests.get(GITHUB_REPO_URL)
    response.raise_for_status()
    
    files_data = response.json()
    md_files = []
    
    for file_info in files_data:
        if file_info["name"] in DOCS_FILES and file_info["name"].endswith(".md"):
            print(f"  Found: {file_info['name']}")
            content_response = requests.get(file_info["download_url"])
            content_response.raise_for_status()
            
            md_files.append({
                "name": file_info["name"],
                "content": content_response.text,
                "size": len(content_response.text)
            })
    
    print(f"  ✓ Fetched {len(md_files)} files")
    return md_files


def upload_files_to_llama_stack(files: List[Dict[str, str]]) -> List[str]:
    """Upload files to Llama Stack Files API."""
    print(f"\n→ Uploading files to Llama Stack...")
    
    file_ids = []
    
    for file_data in files:
        # Upload file using Files API with multipart/form-data
        files_payload = {
            'file': (file_data["name"], file_data["content"], 'text/markdown')
        }
        
        data_payload = {
            'purpose': 'assistants'
        }
        
        response = requests.post(
            f"{LLAMA_STACK_URL}/v1/files",
            files=files_payload,
            data=data_payload
        )
        
        if response.status_code in [200, 201]:
            file_obj = response.json()
            file_id = file_obj.get("id")
            file_ids.append(file_id)
            print(f"  ✓ Uploaded: {file_data['name']} (ID: {file_id})")
        else:
            print(f"  ✗ Failed to upload {file_data['name']}: {response.status_code} - {response.text}")
            continue
    
    return file_ids


def create_vector_store() -> str:
    """Create a vector store in Llama Stack."""
    print(f"\n→ Creating vector store '{VECTOR_STORE_NAME}'...")
    
    # Check if vector store already exists
    list_response = requests.get(f"{LLAMA_STACK_URL}/v1/vector_stores")
    if list_response.status_code == 200:
        existing_stores = list_response.json().get("data", [])
        for store in existing_stores:
            if store.get("name") == VECTOR_STORE_NAME:
                store_id = store.get("id")
                print(f"  ⚠ Vector store already exists (ID: {store_id})")
                return store_id
    
    # Create new vector store
    payload = {
        "name": VECTOR_STORE_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "chunking_strategy": {
            "type": "fixed",
            "chunk_size": 1000,
            "chunk_overlap": 100
        }
    }
    
    response = requests.post(
        f"{LLAMA_STACK_URL}/v1/vector_stores",
        json=payload
    )
    
    if response.status_code in [200, 201]:
        store_obj = response.json()
        store_id = store_obj.get("id")
        print(f"  ✓ Created vector store (ID: {store_id})")
        return store_id
    else:
        print(f"  ✗ Failed to create vector store: {response.status_code} - {response.text}")
        sys.exit(1)


def add_files_to_vector_store(vector_store_id: str, file_ids: List[str]):
    """Add files to the vector store."""
    print(f"\n→ Adding files to vector store...")
    
    for file_id in file_ids:
        payload = {
            "file_id": file_id
        }
        
        response = requests.post(
            f"{LLAMA_STACK_URL}/v1/vector_stores/{vector_store_id}/files",
            json=payload
        )
        
        if response.status_code in [200, 201]:
            print(f"  ✓ Added file {file_id} to vector store")
        else:
            print(f"  ✗ Failed to add file {file_id}: {response.status_code} - {response.text}")
    
    # Wait a bit for indexing
    print(f"\n→ Waiting for vector store indexing...")
    time.sleep(5)
    print(f"  ✓ Indexing should be complete")


def verify_vector_store(vector_store_id: str):
    """Verify the vector store is populated."""
    print(f"\n→ Verifying vector store...")
    
    # Get vector store details
    response = requests.get(f"{LLAMA_STACK_URL}/v1/vector_stores/{vector_store_id}")
    
    if response.status_code == 200:
        store = response.json()
        file_count = store.get("file_counts", {}).get("completed", 0)
        print(f"  ✓ Vector store contains {file_count} files")
        
        # List files in vector store
        files_response = requests.get(f"{LLAMA_STACK_URL}/v1/vector_stores/{vector_store_id}/files")
        if files_response.status_code == 200:
            files = files_response.json().get("data", [])
            print(f"  ✓ Files in vector store: {len(files)}")
        
        return True
    else:
        print(f"  ✗ Failed to verify vector store: {response.status_code}")
        return False


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Llama Stack Vector Store Setup")
    print("=" * 60)
    print(f"Llama Stack URL: {LLAMA_STACK_URL}")
    print(f"Target Repository: varshaprasad96/rh-analyze-prototype")
    print("=" * 60)
    
    try:
        # Step 1: Fetch documentation files
        files = fetch_github_files()
        
        if not files:
            print("\n✗ No files found to upload")
            sys.exit(1)
        
        # Step 2: Upload files to Llama Stack
        file_ids = upload_files_to_llama_stack(files)
        
        if not file_ids:
            print("\n✗ No files were uploaded successfully")
            sys.exit(1)
        
        # Step 3: Create vector store
        vector_store_id = create_vector_store()
        
        # Step 4: Add files to vector store
        add_files_to_vector_store(vector_store_id, file_ids)
        
        # Step 5: Verify
        verify_vector_store(vector_store_id)
        
        # Save vector store ID to a file for ConfigMap creation
        with open("/tmp/vectorstore-id.txt", "w") as f:
            f.write(vector_store_id)
        
        print("\n" + "=" * 60)
        print("✓ Vector store setup complete!")
        print(f"  Vector Store ID: {vector_store_id}")
        print(f"  Files uploaded: {len(file_ids)}")
        print(f"  Saved to: /tmp/vectorstore-id.txt")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

