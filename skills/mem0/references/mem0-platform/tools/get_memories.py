"""
Mem0 Platform -- Get Memories Examples
Reference implementation for retrieving memories via the Mem0 Platform API.
"""

import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

# --- Get Single Memory by ID ---

memory = client.get(memory_id="ea925981-272f-40dd-b576-be64e4871429")
# Returns full memory object with all fields

# --- Get All Memories for a User ---

memories = client.get_all(filters={"AND": [{"user_id": "alice"}]})
# Returns: array of memory objects + total_memories count

# --- Get All with Date Range ---

memories = client.get_all(
    filters={
        "AND": [
            {"user_id": "alex"},
            {"created_at": {"gte": "2024-07-01", "lte": "2024-07-31"}},
        ]
    }
)

# --- Get All with Pagination ---

memories = client.get_all(
    filters={"AND": [{"user_id": "alice"}]},
    page=1,
    page_size=50,
)

# --- Get All with Graph Data ---

memories = client.get_all(
    filters={"AND": [{"user_id": "alice"}]},
    enable_graph=True,
)
# Response includes entities and relations arrays

# --- Get All with Specific Fields ---

memories = client.get_all(
    filters={"AND": [{"user_id": "alice"}]},
    fields=["memory", "categories", "created_at"],
)

# --- Memory History ---

history = client.history(memory_id="ea925981-272f-40dd-b576-be64e4871429")
# Returns array of history entries with previous_value, new_value, action, timestamps

# --- cURL Equivalent (Get Single) ---
"""
curl -X GET https://api.mem0.ai/v1/memories/ea925981-272f-40dd-b576-be64e4871429/ \
  -H "Authorization: Token $MEM0_API_KEY"
"""

# --- cURL Equivalent (Get All) ---
"""
curl -X POST https://api.mem0.ai/v2/memories/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"filters": {"AND": [{"user_id": "alice"}]}, "page": 1, "page_size": 100}'
"""

# Notes:
# - get_all requires at least one entity filter (user_id, agent_id, app_id, or run_id)
# - Default page_size is 100
# - Graph data (entities/relations) only returned when enable_graph=True
