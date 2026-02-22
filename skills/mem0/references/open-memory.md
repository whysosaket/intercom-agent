# OpenMemory

Private, local-first memory server that creates a shared, persistent memory layer for MCP-compatible tools. All data remains local -- no cloud synchronization.

## Status

Documentation links only. The agent should fetch these pages on demand for implementation details.

## Documentation Links

| Topic | URL |
|-------|-----|
| Overview | https://docs.mem0.ai/openmemory/overview |
| Quickstart | https://docs.mem0.ai/openmemory/quickstart |
| GitHub Repository | https://github.com/mem0ai/mem0/tree/main/openmemory |
| Hosted Platform | https://app.openmemory.dev |

## Key Characteristics

- Local-first: all data stays on your machine
- Requires Docker and OpenAI API key
- 4 core tools: `add_memories`, `search_memory`, `list_memories`, `delete_all_memories`
- Supported clients: Cursor, Claude Desktop, Windsurf, Cline
- Install via: `curl -sL https://raw.githubusercontent.com/mem0ai/mem0/main/openmemory/run.sh | bash`
- Hosted variant: `npx @openmemory/install --client claude --env OPENMEMORY_API_KEY=your-key`

## When to Use OpenMemory

Use the doc search tool (`scripts/mem0_doc_search.py`) to fetch specific implementation details on demand rather than storing them locally.
