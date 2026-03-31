# MCP-Memory

An ontology-based external memory system for AI, built on the [Model Context Protocol](https://modelcontextprotocol.io/).

Designed so AI can reason over structured knowledge — not just retrieve it.

## Key Numbers

- **4,600+** nodes across **25** semantic types
- **6,700+** edges with **49** relation rules
- Hybrid search: Vector (ChromaDB) + Full-text (FTS5 trigram) + Graph (NetworkX)

## Architecture

```
MCP Server (server.py)
├── tools/          13 MCP tools (remember, recall, get_context, promote, ...)
├── storage/        SQLite + FTS5 + ChromaDB + NetworkX
├── enrichment/     5-phase LLM enrichment pipeline (25 prompts)
├── ontology/       Schema definition + validators
├── embedding/      OpenAI embedding integration
├── graph/          Graph traversal + relationship reasoning
└── scripts/        Batch processing, evaluation, migration
```

## Tools

| Tool | Purpose |
|------|---------|
| `remember` | Store knowledge with automatic type inference |
| `recall` | Hybrid search across all storage layers |
| `get_context` | Session-aware context assembly |
| `promote_node` | 3-gate promotion pipeline (SWR → Bayesian → MDL) |
| `save_session` | Narrative + Decision + Question extraction |
| `analyze_signals` | Pattern detection across recent observations |
| `inspect` | Deep-dive into node relationships |

## Stack

Python · SQLite · FTS5 · ChromaDB · NetworkX · MCP Protocol
