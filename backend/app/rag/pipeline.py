"""RAG pipeline: chunking, indexing and relevance-ranked context construction for agents."""

from dataclasses import dataclass

from app.rag.vectorstore import RetrievedChunk, VectorStore

MAX_CHUNK_CHARS = 900
CHUNK_OVERLAP = 120


@dataclass
class ContextBlock:
    artifact_type: str
    source: str
    version: int
    score: float
    text: str

    def render(self) -> str:
        header = f"[source: {self.artifact_type} v{self.version} ({self.source}) | relevance: {self.score:.2f}]"
        return f"{header}\n{self.text}"


def chunk_text(text: str) -> list[str]:
    """Split content into overlapping chunks for indexing."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + MAX_CHUNK_CHARS // 2, end)
            if boundary > start:
                end = boundary
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP if end < len(text) else end
    return [c for c in chunks if c]


class RAGPipeline:
    def __init__(self, store: VectorStore | None = None):
        self.store = store or VectorStore()

    def index_artifact(
        self,
        project_id: int,
        artifact_type: str,
        artifact_id: int,
        version: int,
        stage: str,
        source: str,
        text: str,
        metadata: dict | None = None,
    ) -> int:
        """Chunk + index a project artifact. Returns number of chunks indexed."""
        count = 0
        for chunk in chunk_text(text):
            self.store.add(
                project_id=project_id,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                version=version,
                stage=stage,
                source=source,
                text=chunk,
                metadata=metadata,
            )
            count += 1
        return count

    def retrieve(
        self,
        project_id: int,
        query: str,
        artifact_types: list[str] | None = None,
        stage: str | None = None,
        top_k: int | None = None,
    ) -> list[ContextBlock]:
        """Retrieve relevant project context, ranked by relevance."""
        results: list[RetrievedChunk] = self.store.search(
            project_id=project_id,
            query=query,
            artifact_types=artifact_types,
            stage=stage,
            top_k=top_k,
        )
        return [
            ContextBlock(
                artifact_type=r.artifact_type,
                source=r.source,
                version=r.version,
                score=r.score,
                text=r.text,
            )
            for r in results
        ]

    def build_context_section(self, blocks: list[ContextBlock]) -> str:
        if not blocks:
            return "(no retrieved project context available for this task)"
        return "\n\n".join(b.render() for b in blocks)


# Shared pipeline instance
rag_pipeline = RAGPipeline()
