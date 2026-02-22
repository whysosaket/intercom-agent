"""
Mem0 Platform -- Search Memory Examples
Reference implementation for searching memories via the Mem0 Platform API.
"""

import os
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

# --- Basic Search ---

results = client.search("What are my dietary restrictions?", user_id="user123")
# Returns: {"memories": [{"id": "...", "memory": "...", "score": 0.89, ...}]}

# --- Search with V2 Filters ---

results = client.search(
    query="What are Alice's hobbies?",
    filters={
        "OR": [
            {"user_id": "alice"},
            {"agent_id": {"in": ["travel-agent", "sports-agent"]}},
        ]
    },
)

# --- Search with Category Filter (partial match) ---

results = client.search(
    query="What are my financial goals?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"categories": {"contains": "finance"}},
        ]
    },
)

# --- Search with Category Filter (exact match) ---

results = client.search(
    query="What personal information do you have?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"categories": {"in": ["personal_information"]}},
        ]
    },
)

# --- Search with Date Range ---

results = client.search(
    query="Recent updates",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
            {"created_at": {"lt": "2024-02-01T00:00:00Z"}},
        ]
    },
)

# --- Search with Reranking ---

results = client.search(
    query="dietary preferences",
    user_id="user123",
    top_k=5,
    rerank=True,
    threshold=0.5,
)

# --- Search with Graph Relations ---

results = client.search(
    query="what is my name?",
    user_id="joseph",
    enable_graph=True,
)
# Response includes "relations" array with entity relationships

# --- Search with Keyword Mode ---

results = client.search(
    query="vegetarian",
    user_id="user123",
    keyword_search=True,
)

# --- Search with Wildcard (any non-null run) ---

results = client.search(
    query="hobbies?",
    filters={
        "AND": [
            {"user_id": "alice"},
            {"run_id": "*"},
        ]
    },
)

# --- Multi-dimensional Query ---

results = client.search(
    query="invoice details",
    filters={
        "AND": [
            {"user_id": "user_123"},
            {"keywords": {"icontains": "invoice"}},
            {"categories": {"in": ["finance"]}},
            {"created_at": {"gte": "2024-01-01T00:00:00Z"}},
            {"created_at": {"lt": "2024-04-01T00:00:00Z"}},
        ]
    },
)

# --- cURL Equivalent ---
"""
curl -X POST https://api.mem0.ai/v2/memories/search/ \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "dietary restrictions", "filters": {"user_id": "user123"}}'
"""
