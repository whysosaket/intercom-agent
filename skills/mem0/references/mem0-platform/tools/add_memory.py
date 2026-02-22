"""
Mem0 Platform -- Add Memory Examples
Reference implementation for adding memories via the Mem0 Platform API.
"""

import os
import requests
from mem0 import MemoryClient

# --- SDK Initialization ---

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

# --- Basic Add ---

messages = [
    {"role": "user", "content": "I'm a vegetarian and allergic to nuts."},
    {"role": "assistant", "content": "Got it! I'll remember your dietary preferences."},
]
result = client.add(messages, user_id="user123")
# Returns: [{"id": "mem_...", "event": "ADD", "data": {"memory": "..."}}]

# --- Add with Metadata ---

result = client.add(
    messages,
    user_id="user123",
    metadata={"source": "onboarding_form", "confidence": "high"},
)

# --- Add with Graph Memory (Pro Plan) ---

result = client.add(
    messages,
    user_id="user123",
    enable_graph=True,
)

# --- Add Immutable Memory ---

result = client.add(
    messages,
    user_id="user123",
    immutable=True,
)

# --- Add with Expiration ---

result = client.add(
    messages,
    user_id="user123",
    expiration_date="2025-12-31",
)

# --- Add with Selective Extraction ---

result = client.add(
    messages,
    user_id="user123",
    includes="dietary preferences",
    excludes="payment information",
)

# --- Add with Agent Scoping ---

result = client.add(
    messages,
    user_id="user123",
    agent_id="nutrition-agent",
    run_id="session-456",
)

# --- Synchronous Add (wait for processing) ---

result = client.add(
    messages,
    user_id="user123",
    async_mode=False,
)

# --- Raw Text (skip inference) ---

result = client.add(
    [{"role": "user", "content": "User prefers dark mode."}],
    user_id="user123",
    infer=False,  # Stores text as-is without LLM inference
)

# --- cURL Equivalent ---
"""
curl -X POST https://api.mem0.ai/v1/memories/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I moved to Austin last month."}
    ],
    "user_id": "alice",
    "metadata": {"source": "onboarding_form"}
  }'
"""
