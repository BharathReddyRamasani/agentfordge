"""Persistent per-project vector store with cosine-similarity retrieval and metadata filtering."""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.rag.embeddings import get_embedding


@dataclass
class Chunk:
    chunk_id: str
    project_id: int
    artifact_type: str
    artifact_id: int
    version: int
    stage: str
    source: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk(Chunk):
    score: float = 0.0


class VectorStore:
    """File-backed vector index. One JSON namespace file per project."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.rag_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.embedding = get_embedding()

    def _namespace_path(self, project_id: int) -> Path:
        return self.base_dir / f"project_{project_id}.json"

    def _load(self, project_id: int) -> dict:
        path = self._namespace_path(project_id)
        if not path.exists():
            return {"chunks": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"chunks": []}

    def _save(self, project_id: int, data: dict) -> None:
        path = self._namespace_path(project_id)
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def add(
        self,
        project_id: int,
        artifact_type: str,
        artifact_id: int,
        version: int,
        stage: str,
        source: str,
        text: str,
        metadata: dict | None = None,
    ) -> str:
        """Index a chunk of project content. Returns the chunk id."""
        data = self._load(project_id)
        chunk_id = uuid.uuid4().hex[:16]
        data["chunks"].append(
            {
                "chunk_id": chunk_id,
                "project_id": project_id,
                "artifact_type": artifact_type,
                "artifact_id": artifact_id,
                "version": version,
                "stage": stage,
                "source": source,
                "text": text,
                "metadata": metadata or {},
            }
        )
        self._save(project_id, data)
        return chunk_id

    def _chunks(self, project_id: int) -> list[Chunk]:
        raw = self._load(project_id).get("chunks", [])
        return [
            Chunk(
                chunk_id=c["chunk_id"],
                project_id=c["project_id"],
                artifact_type=c["artifact_type"],
                artifact_id=c["artifact_id"],
                version=c["version"],
                stage=c["stage"],
                source=c["source"],
                text=c["text"],
                metadata=c.get("metadata", {}),
            )
            for c in raw
        ]

    def search(
        self,
        project_id: int,
        query: str,
        artifact_types: list[str] | None = None,
        stage: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve the most relevant chunks with cosine-similarity ranking."""
        top_k = top_k or settings.rag_top_k
        candidates = [
            c
            for c in self._chunks(project_id)
            if (artifact_types is None or c.artifact_type in artifact_types)
            and (stage is None or c.stage == stage)
        ]
        if not candidates:
            return []
        corpus = [c.text for c in candidates] + [query]
        matrix = self.embedding.embed([c.text for c in candidates] + [query], corpus=corpus)
        query_vec = matrix[-1]
        doc_vecs = matrix[:-1]
        doc_norms = np.linalg.norm(doc_vecs, axis=1)
        query_norm = np.linalg.norm(query_vec) or 1.0
        scores = np.zeros(len(candidates), dtype=np.float32)
        nonzero = doc_norms > 0
        scores[nonzero] = (doc_vecs[nonzero] @ query_vec) / (doc_norms[nonzero] * query_norm)
        order = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in order:
            chunk = candidates[int(idx)]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    project_id=chunk.project_id,
                    artifact_type=chunk.artifact_type,
                    artifact_id=chunk.artifact_id,
                    version=chunk.version,
                    stage=chunk.stage,
                    source=chunk.source,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    score=float(scores[int(idx)]),
                )
            )
        return results

    def clear(self, project_id: int) -> None:
        path = self._namespace_path(project_id)
        if path.exists():
            path.unlink()

    def count(self, project_id: int) -> int:
        return len(self._load(project_id).get("chunks", []))
