"""
Mem0 Platform -- Update Memory Examples
Reference implementation for updating memories via the Mem0 Platform API.
"""

import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

# --- Update Text Content ---

result = client.update(
    memory_id="ea925981-272f-40dd-b576-be64e4871429",
    text="Updated dietary info: vegan since 2024",
)

# --- Update Metadata ---

result = client.update(
    memory_id="ea925981-272f-40dd-b576-be64e4871429",
    text="Vegan since January 2024",
    metadata={"verified": True, "source": "user_correction"},
)

# --- cURL Equivalent ---
"""
curl -X PUT https://api.mem0.ai/v1/memories/ea925981-272f-40dd-b576-be64e4871429/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Updated text", "metadata": {"verified": true}}'
"""

# Notes:
# - Cannot update immutable memories (created with immutable=True)
# - Updates change the hash field
# - Returns full updated memory object with new updated_at timestamp
