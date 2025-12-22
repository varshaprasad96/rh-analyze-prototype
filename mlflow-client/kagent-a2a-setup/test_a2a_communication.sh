#!/bin/bash
# Test Agent-to-Agent communication via A2A protocol

echo "=========================================="
echo "Agent-to-Agent A2A Communication Test"
echo "=========================================="
echo

AGENT1_URL="http://localhost:8080"  # llamastack-a2a-agent
AGENT2_URL="http://localhost:8081"  # rh-analyze-simple

echo "Agent 1 (llamastack-a2a-agent): $AGENT1_URL"
echo "Agent 2 (rh-analyze-simple): $AGENT2_URL"
echo

# Test 1: Agent 1 calls Agent 2
echo "Test 1: Agent 1 asking Agent 2 via A2A..."
echo "Question: 'What is kagent?'"
echo

RESPONSE1=$(curl -s -X POST "$AGENT2_URL/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-a2a-1",
        "role": "user",
        "parts": [{"kind": "text", "text": "What is kagent?"}]
      }
    }
  }')

echo "$RESPONSE1" | python3 -m json.tool | head -40
echo

# Extract answer from response
ANSWER1=$(echo "$RESPONSE1" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('result', {}).get('artifacts', [{}])[0].get('parts', [{}])[0].get('text', 'No answer found'))" 2>/dev/null)
echo "Agent 2 Answer: $ANSWER1"
echo
echo "----------------------------------------"
echo

# Test 2: Agent 2 calls Agent 1
echo "Test 2: Agent 2 asking Agent 1 via A2A..."
echo "Question: 'What is Llamastack?'"
echo

RESPONSE2=$(curl -s -X POST "$AGENT1_URL/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg-a2a-2",
        "role": "user",
        "parts": [{"kind": "text", "text": "What is Llamastack?"}]
      }
    }
  }')

echo "$RESPONSE2" | python3 -m json.tool | head -40
echo

# Extract answer from response
ANSWER2=$(echo "$RESPONSE2" | python3 -c "import sys, json; data=json.load(sys.stdin); result=data.get('result', {}); artifacts=result.get('artifacts', []); print(artifacts[0].get('parts', [{}])[0].get('text', 'No answer found') if artifacts else result.get('history', [{}])[-1].get('parts', [{}])[0].get('text', 'No answer found'))" 2>/dev/null)
echo "Agent 1 Answer: $ANSWER2"
echo
echo "=========================================="
echo "A2A Communication Test Complete!"
echo "=========================================="

