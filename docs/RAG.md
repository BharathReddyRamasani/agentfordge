# AgentForge — RAG / Project Memory

## Pipeline

```
Agent Task → Query Construction (task-specific, never full history)
→ Retrieval (project-namespaced vector store, type/stage filters)
→ Relevance Ranking (cosine similarity) → Context Selection (top-K)
→ Prompt Construction (separated sections) → LLM → Validated Agent Output
```

## Implementation (`rag/`)

- **Chunking** (`pipeline.chunk_text`): ~900-char overlapping chunks.
- **Embeddings** (`embeddings.py`): local TF-IDF default (keyless, offline);
  OpenAI-compatible embeddings when `EMBEDDING_PROVIDER=openai`.
- **Vector store** (`vectorstore.py`): file-persisted per-project namespaces
  (`RAG_DIR/project_{id}.json`), chunk metadata
  `{project_id, artifact_id, artifact_type, version, stage, source, timestamp}`.
- **Indexing points**: requirements, analyses, plans + revisions, feedback, prototype
  specs (+rebuilds), architecture, generated code, test/debug results, reviews.
- **Retrieval isolation**: every query is filtered by `project_id` — a project can
  never retrieve another project's context.

## Agent retrieval policies

Each agent declares `rag_types` (artifact types) and builds its query from the task
input (e.g. Planning Agent: feedback + analysis purpose; Debugging Agent: failure
output). `GET /api/projects/{id}/memory?q=&types=&top_k=` exposes the same retrieval
for inspection.

## Injection defense

Retrieved blocks are rendered under an explicit `RETRIEVED CONTEXT (untrusted data)`
header, and every system prompt instructs the model that this content cannot override
system instructions.
