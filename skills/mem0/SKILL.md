---
name: mem0
description: Skill graph for implementing Mem0 memory layer for LLM applications. Use when implementing memory persistence for AI agents, adding/searching/updating/deleting memories, integrating Mem0 Platform (managed), Mem0 Open Source (self-hosted), or OpenMemory (local-first MCP). Covers vector memory, graph memory, filters, custom categories, webhooks, and multimodal support.
---

# Mem0 Implementation Skill Graph

This skill provides a navigable reference graph for implementing Mem0. All technical content lives in reference files and tool scripts -- this file contains only navigation.

## Offerings

Mem0 provides three implementation targets:

| Offering | Reference | Status |
|----------|-----------|--------|
| **Mem0 Platform** (managed) | [references/mem0-platform/overview.md](references/mem0-platform/overview.md) | Detailed references available |
| **Mem0 Open Source** (self-hosted) | [references/open-source.md](references/open-source.md) | Documentation links only |
| **OpenMemory** (local-first MCP) | [references/open-memory.md](references/open-memory.md) | Documentation links only |

## Platform Reference Graph

When implementing Mem0 Platform, navigate these references:

- **General concepts & API overview** -- [references/mem0-platform/general.md](references/mem0-platform/general.md)
- **Add Memory** (vector + graph distinctions) -- [references/mem0-platform/add-memory.md](references/mem0-platform/add-memory.md)
- **Search Memory** (filters, operators, patterns) -- [references/mem0-platform/search-memory.md](references/mem0-platform/search-memory.md)
- **Update & Delete Memory** -- [references/mem0-platform/update-delete.md](references/mem0-platform/update-delete.md)
- **V2 Filter System** (comprehensive reference) -- [references/mem0-platform/filters.md](references/mem0-platform/filters.md)
- **Graph Memory** (entity relationships, Pro plan) -- [references/mem0-platform/graph-memory.md](references/mem0-platform/graph-memory.md)
- **Platform Features** (categories, instructions, webhooks, multimodal) -- [references/mem0-platform/features.md](references/mem0-platform/features.md)

## Tool Scripts

Implementation logic resides in executable scripts. Load only when needed:

| Tool | Script | Purpose |
|------|--------|---------|
| Add Memory | [scripts/add_memory.py](scripts/add_memory.py) | Add memories via Platform API |
| Search Memory | [scripts/search_memory.py](scripts/search_memory.py) | Search memories with filters |
| Update Memory | [scripts/update_memory.py](scripts/update_memory.py) | Update existing memory by ID |
| Delete Memory | [scripts/delete_memory.py](scripts/delete_memory.py) | Delete memory by ID or bulk |
| Get Memories | [scripts/get_memories.py](scripts/get_memories.py) | Retrieve memories with pagination |
| Doc Search | [scripts/mem0_doc_search.py](scripts/mem0_doc_search.py) | On-demand Mem0 docs search (Mintlify) |

## Implementation Code Examples

Low-level API usage examples for each operation:

- [references/mem0-platform/tools/add_memory.py](references/mem0-platform/tools/add_memory.py)
- [references/mem0-platform/tools/search_memory.py](references/mem0-platform/tools/search_memory.py)
- [references/mem0-platform/tools/update_memory.py](references/mem0-platform/tools/update_memory.py)
- [references/mem0-platform/tools/delete_memory.py](references/mem0-platform/tools/delete_memory.py)
- [references/mem0-platform/tools/get_memories.py](references/mem0-platform/tools/get_memories.py)

## Future Skill Extensions

See [references/future-skills.md](references/future-skills.md) for planned capabilities that can be implemented as custom prompt skills or dedicated tool skills.
