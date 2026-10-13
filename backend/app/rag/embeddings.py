"""RAG embedding backends. Local TF-IDF by default; OpenAI-compatible API optional."""

import json
import math
import re
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import settings

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BaseEmbedding(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str], corpus: list[str] | None = None) -> np.ndarray:
        """Return an (n, dim) matrix of embeddings for texts."""


class TfidfEmbedding(BaseEmbedding):
    """Local TF-IDF embeddings. Vocabulary + IDF are fitted on the provided corpus."""

    name = "tfidf"

    def _fit(self, corpus: list[str]) -> tuple[dict[str, int], np.ndarray]:
        vocab: dict[str, int] = {}
        for doc in corpus:
            for tok in set(tokenize(doc)):
                if tok not in vocab:
                    vocab[tok] = len(vocab)
        n_docs = max(len(corpus), 1)
        idf = np.zeros(len(vocab), dtype=np.float32)
        for tok, idx in vocab.items():
            df = sum(1 for doc in corpus if tok in set(tokenize(doc)))
            idf[idx] = math.log((1 + n_docs) / (1 + df)) + 1.0
        return vocab, idf

    def embed(self, texts: list[str], corpus: list[str] | None = None) -> np.ndarray:
        fit_corpus = corpus if corpus else list(texts)
        vocab, idf = self._fit(fit_corpus)
        dim = max(len(vocab), 1)
        matrix = np.zeros((len(texts), dim), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = tokenize(text)
            if not tokens:
                continue
            counts: dict[int, int] = {}
            for tok in tokens:
                idx = vocab.get(tok)
                if idx is not None:
                    counts[idx] = counts.get(idx, 0) + 1
            total = sum(counts.values()) or 1
            for idx, count in counts.items():
                matrix[i, idx] = (count / total) * idf[idx]
        return matrix


class OpenAIEmbedding(BaseEmbedding):
    """Embeddings via an OpenAI-compatible API (requires LLM_API_KEY)."""

    name = "openai"

    def embed(self, texts: list[str], corpus: list[str] | None = None) -> np.ndarray:
        import httpx

        from app.core.config import settings as s

        api_key = s.llm_api_key
        if not api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requires LLM_API_KEY")
        base = (s.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        resp = httpx.post(
            f"{base}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": s.embedding_model or "text-embedding-3-small", "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        vectors = sorted(data, key=lambda d: d["index"])
        return np.array([v["embedding"] for v in vectors], dtype=np.float32)


def get_embedding() -> BaseEmbedding:
    provider = (settings.embedding_provider or "tfidf").lower()
    if provider == "openai":
        return OpenAIEmbedding()
    return TfidfEmbedding()


def dump_json(obj) -> str:
    return json.dumps(obj, default=str)
