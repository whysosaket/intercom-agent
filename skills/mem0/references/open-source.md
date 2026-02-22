# Mem0 Open Source

Self-hosted Mem0 stack for full control over data, deployment, and customization.

## Status

Documentation links only. The agent should fetch these pages on demand for implementation details.

## Documentation Links

| Topic | URL |
|-------|-----|
| Overview | https://docs.mem0.ai/open-source/overview |
| Python Quickstart | https://docs.mem0.ai/open-source/python-quickstart |
| Node.js Quickstart | https://docs.mem0.ai/open-source/node-quickstart |
| Features | https://docs.mem0.ai/open-source/features |
| Graph Memory | https://docs.mem0.ai/open-source/features/graph-memory |
| REST API | https://docs.mem0.ai/open-source/features/rest-api |
| Custom Fact Extraction | https://docs.mem0.ai/open-source/features/custom-fact-extraction |
| Custom Memory Updates | https://docs.mem0.ai/open-source/features/custom-memory-update |
| Async Operations | https://docs.mem0.ai/open-source/features/async-memory-operations |
| Multimodal Support | https://docs.mem0.ai/open-source/features/multimodal-support |
| Configure Components | https://docs.mem0.ai/open-source/configure-components |
| Cookbooks | https://docs.mem0.ai/cookbooks |

## Key Characteristics

- Requires OpenAI API key by default (supports Ollama, Anthropic, local models via config)
- Default stack: OpenAI LLM + text-embedding-3-small + local Qdrant + SQLite history
- All components customizable via `Memory.from_config()`
- Python: `from mem0 import Memory` / Node.js: `import { Memory } from "mem0ai/oss"`
- Supports 18 LLMs, 18 vector databases, 10 embedding providers
- Graph memory via Neo4j, Memgraph, Neptune, or Kuzu

## When to Use Open Source

Use the doc search tool (`scripts/mem0_doc_search.py`) to fetch specific implementation details on demand rather than storing them locally.
