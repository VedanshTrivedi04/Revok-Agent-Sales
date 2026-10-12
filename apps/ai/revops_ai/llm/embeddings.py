"""Embedding client for Riddhi's retrieval index: a self-hosted OpenAI-compatible /embeddings
endpoint (Ollama, llama.cpp, TEI, vLLM). Record text is never sent to a hosted vendor
(scripts/egress_check.py checks EMBED_BASE_URL like LLM_BASE_URL). Texts are never logged.
"""

import hashlib
import math
import re
from typing import Protocol

from openai import AsyncOpenAI

from revops_ai.config import Settings, get_settings

BATCH = 16


class EmbeddingError(Exception):
    """The endpoint answered with vectors of the wrong size."""


class Embedder(Protocol):
    model: str

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class OpenAICompatEmbedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self.model = self.s.embed_model
        self.client = AsyncOpenAI(
            base_url=self.s.embed_base_url, api_key=self.s.embed_api_key, timeout=60.0
        )

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(inputs), BATCH):
            resp = await self.client.embeddings.create(
                model=self.model, input=inputs[i : i + BATCH], encoding_format="float"
            )
            for item in sorted(resp.data, key=lambda d: d.index):
                if len(item.embedding) != self.s.embed_dim:
                    raise EmbeddingError(
                        f"{self.model} returned {len(item.embedding)} numbers, "
                        f"EMBED_DIM is {self.s.embed_dim}"
                    )
                out.append(list(item.embedding))
        return out

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed([self.s.embed_doc_prefix + t for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([self.s.embed_query_prefix + text]))[0]


class FakeEmbedder:
    """Deterministic embeddings for tests: a hashed bag of words, so texts that share words are
    close and unrelated texts are not. No model, no network."""

    def __init__(self, dim: int = 768, model: str = "fake-embed") -> None:
        self.dim, self.model = dim, model
        self.calls: list[list[str]] = []

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._one(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        self.calls.append([text])
        return self._one(text)
