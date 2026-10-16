"""Embedding providers for optional dense semantic retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import math
from typing import Sequence

from ..config import Config


class EmbeddingProvider(ABC):
    """Abstract interface for dense embedding generation."""

    @abstractmethod
    def embed(self, text: str) -> tuple[float, ...]: ...

    def embed_batch(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self.embed(t) for t in texts]

    @property
    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class NoOpEmbeddingProvider(EmbeddingProvider):
    """Fallback provider when no embedding client or key is configured; uses pure BM25."""

    def embed(self, text: str) -> tuple[float, ...]:
        return ()

    @property
    def is_available(self) -> bool:
        return False

    @property
    def model_name(self) -> str:
        return "none"


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline embedding provider for offline verification and testing.
    
    Generates a normalized 64-dimensional pseudo-embedding from word/character n-grams.
    """

    def __init__(self, dimension: int = 64) -> None:
        self.dim = dimension

    def embed(self, text: str) -> tuple[float, ...]:
        if not text or not text.strip():
            return tuple([0.0] * self.dim)

        vector = [0.0] * self.dim
        tokens = text.casefold().split()
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            for idx in range(min(len(digest), self.dim)):
                vector[idx] += (digest[idx] - 128) / 128.0

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return tuple(vector)

    @property
    def is_available(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "mock-deterministic-64d"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Dense embedding provider using the Gemini text-embedding-004 model via google-genai."""

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-004") -> None:
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model = model
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    def embed(self, text: str) -> tuple[float, ...]:
        if not self.is_available or not text or not text.strip():
            return ()
        try:
            response = self._client.models.embed_content(
                model=self.model,
                contents=text,
            )
            embedding_vals = getattr(response, "embedding", None)
            if embedding_vals and hasattr(embedding_vals, "values"):
                vals = list(embedding_vals.values)
                # L2 normalize
                norm = math.sqrt(sum(v * v for v in vals))
                if norm > 0:
                    vals = [v / norm for v in vals]
                return tuple(vals)
        except Exception:
            return ()
        return ()

    @property
    def is_available(self) -> bool:
        return self._client is not None

    @property
    def model_name(self) -> str:
        return self.model
