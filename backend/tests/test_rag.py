"""RAG pipeline: chunking, indexing, relevance-ranked retrieval with metadata filters."""

import tempfile

from app.rag.pipeline import RAGPipeline, chunk_text
from app.rag.vectorstore import VectorStore


def test_chunk_text_splits_long_content():
    long_text = "Requirement analysis. " * 200
    chunks = chunk_text(long_text)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    assert chunk_text("") == []
    assert len(chunk_text("short")) == 1


def test_vector_store_retrieval_ranking():
    store = VectorStore(base_dir=tempfile.mkdtemp())
    store.add(1, "plan", 0, 1, "plan", "planning", "The prototype has login, dashboard and appointment booking screens")
    store.add(1, "test_results", 0, 1, "testing", "tests", "Pytest suite executed against the backend API")
    results = store.search(1, "prototype screens login dashboard")
    assert len(results) == 2
    assert results[0].artifact_type == "plan"
    assert results[0].score >= results[1].score
    assert results[0].source == "planning"
    assert results[0].version == 1


def test_vector_store_metadata_filtering():
    store = VectorStore(base_dir=tempfile.mkdtemp())
    store.add(1, "plan", 0, 1, "plan", "planning", "appointment booking flow")
    store.add(1, "feedback", 0, 1, "prototype", "user", "please change the color scheme")
    results = store.search(1, "appointment", artifact_types=["plan"])
    assert len(results) == 1
    assert results[0].artifact_type == "plan"


def test_rag_pipeline_end_to_end():
    pipeline = RAGPipeline(VectorStore(base_dir=tempfile.mkdtemp()))
    count = pipeline.index_artifact(7, "requirement", 1, 1, "analyze", "user", "Hospital system with patient registration and doctor appointments")
    assert count >= 1
    blocks = pipeline.retrieve(7, "patient registration")
    assert len(blocks) >= 1
    rendered = pipeline.build_context_section(blocks)
    assert "requirement" in rendered
    assert pipeline.build_context_section([]).startswith("(no retrieved")
