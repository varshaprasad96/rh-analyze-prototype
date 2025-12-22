#!/usr/bin/env python3
"""
Test Agent-to-Agent communication using A2A protocol

This script demonstrates how one agent can call another agent via A2A protocol.
"""

import os
import sys
import requests
import json

def get_agent_card(agent_url):
    """Get agent card (A2A discovery)"""
    try:
        response = requests.get(
            f"{agent_url}/.well-known/agent.json",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ⚠ Failed to get agent card (status: {response.status_code})")
            return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None

def call_agent(agent_url, message, skill="answer"):
    """Call an agent via A2A protocol"""
    try:
        response = requests.post(
            f"{agent_url}/",
            json={
                "message": message,
                "skill": skill
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ⚠ Failed (status: {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None

def test_agent_to_agent():
    """Test agent-to-agent communication"""
    
    # Agent URLs (update these based on your port-forwards or service URLs)
    agent1_url = os.getenv("AGENT1_URL", "http://localhost:8080")  # llamastack-a2a-agent
    agent2_url = os.getenv("AGENT2_URL", "http://localhost:8081")  # rh-analyze-simple or other
    
    print("=" * 70)
    print("Agent-to-Agent Communication Test (A2A Protocol)")
    print("=" * 70)
    print()
    
    # Step 1: Discover Agent 1 capabilities
    print("Step 1: Discovering Agent 1 capabilities...")
    print(f"Agent 1 URL: {agent1_url}")
    agent1_card = get_agent_card(agent1_url)
    if agent1_card:
        print(f"   ✓ Agent 1: {agent1_card.get('name', 'Unknown')}")
        print(f"   Description: {agent1_card.get('description', 'N/A')}")
        skills = agent1_card.get('skills', [])
        if skills:
            print(f"   Skills: {[s.get('id') for s in skills]}")
    print()
    
    # Step 2: Discover Agent 2 capabilities
    print("Step 2: Discovering Agent 2 capabilities...")
    print(f"Agent 2 URL: {agent2_url}")
    agent2_card = get_agent_card(agent2_url)
    if agent2_card:
        print(f"   ✓ Agent 2: {agent2_card.get('name', 'Unknown')}")
        print(f"   Description: {agent2_card.get('description', 'N/A')}")
        skills = agent2_card.get('skills', [])
        if skills:
            print(f"   Skills: {[s.get('id') for s in skills]}")
    print()
    
    # Step 3: Agent 1 asks Agent 2 a question
    print("Step 3: Agent 1 asking Agent 2 a question...")
    print("   Message: 'What is kagent?'")
    agent2_response = call_agent(agent2_url, "What is kagent?", "answer")
    if agent2_response:
        print(f"   ✓ Agent 2 Response: {json.dumps(agent2_response, indent=4)}")
    print()
    
    # Step 4: Agent 2 asks Agent 1 a question
    print("Step 4: Agent 2 asking Agent 1 a question...")
    print("   Message: 'What is Llamastack?'")
    agent1_response = call_agent(agent1_url, "What is Llamastack?", "answer")
    if agent1_response:
        print(f"   ✓ Agent 1 Response: {json.dumps(agent1_response, indent=4)}")
    print()
    
    # Step 5: Orchestration example - Agent 1 delegates to Agent 2
    print("Step 5: Orchestration - Agent 1 delegates task to Agent 2...")
    print("   Agent 1 receives: 'Can you help me understand Kubernetes agents?'")
    print("   Agent 1 decides to delegate to Agent 2 (kagent expert)...")
    
    # Agent 1 could analyze and decide to delegate
    delegation_message = "The user asked about Kubernetes agents. Can you explain what kagent is?"
    agent2_delegated = call_agent(agent2_url, delegation_message, "answer")
    if agent2_delegated:
        print(f"   ✓ Agent 2 (delegated) Response: {json.dumps(agent2_delegated, indent=4)}")
    
    print()
    print("=" * 70)
    print("Agent-to-Agent Communication Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    test_agent_to_agent()

