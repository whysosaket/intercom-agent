"""
Mem0 Platform -- Delete Memory Examples
Reference implementation for deleting memories via the Mem0 Platform API.
"""

import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

# --- Delete Single Memory ---

client.delete(memory_id="ea925981-272f-40dd-b576-be64e4871429")
# Returns: {"message": "Memory deleted successfully!"}

# --- Delete All Memories for a User ---

client.delete_all(user_id="alice")
# Warning: Irreversible operation

# --- Delete All Memories for an Agent ---

client.delete_all(agent_id="nutrition-agent")

# --- Delete All for a Run/Session ---

client.delete_all(run_id="session-456")

# --- cURL Equivalent ---
"""
curl -X DELETE https://api.mem0.ai/v1/memories/ea925981-272f-40dd-b576-be64e4871429/ \
  -H "Authorization: Token $MEM0_API_KEY"
"""

# Notes:
# - Single delete returns 204 status with confirmation message
# - delete_all has no dedicated REST endpoint; SDK iterates internally
# - All deletes are irreversible
# - Can scope by user_id, agent_id, app_id, or run_id
