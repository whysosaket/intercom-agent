# Mem0 Platform Overview

Fully managed memory layer for AI agents -- production-ready in minutes. No infrastructure provisioning required.

## Quick Navigation

| Topic | Reference File |
|-------|---------------|
| General concepts & API surface | [general.md](general.md) |
| Add Memory (vector + graph) | [add-memory.md](add-memory.md) |
| Search Memory (filters, operators) | [search-memory.md](search-memory.md) |
| Update & Delete Memory | [update-delete.md](update-delete.md) |
| V2 Filter System | [filters.md](filters.md) |
| Graph Memory (Pro plan) | [graph-memory.md](graph-memory.md) |
| Platform Features (categories, webhooks, etc.) | [features.md](features.md) |
| Code Examples | [tools/](tools/) directory |

## Infrastructure (Managed)

- Vector stores, graph services, reranking -- all managed internally
- SOC 2 Type II certified, GDPR compliant
- Audit logging, workspace governance, enterprise access management
- Automatic scaling and high availability

## Access Points

- Dashboard: https://app.mem0.ai
- API Base URL: `https://api.mem0.ai/`
- LLM-friendly docs index: https://docs.mem0.ai/llms.txt
- API key management: https://app.mem0.ai/dashboard/settings?tab=api-keys

## SDK Installation

```
pip install mem0ai       # Python 3.10+
npm install mem0ai       # Node.js 14+
```

## Authentication

All endpoints use header-based token auth:
```
Authorization: Token <MEM0_API_KEY>
```

## Integrations

LangChain, CrewAI, Vercel AI SDK, MCP, LangGraph, LlamaIndex, AutoGen, Flowise, Dify
