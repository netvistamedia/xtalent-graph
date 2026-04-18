"""Semantic search over profile roots.

The index is a derived view over published CVs. It depends on two pluggable
interfaces:

* :class:`Embedder`    — turns a text string into a dense vector.
* :class:`VectorIndex` — stores vectors with metadata and answers KNN queries.

Reference implementations (:class:`DeterministicEmbedder`,
:class:`InMemoryVectorIndex`) are good enough for tests, demos, and small
deployments. Production setups swap in real providers (Grok / OpenAI / Voyage
for embeddings; Qdrant / pgvector / Pinecone for the index) behind the same
interfaces.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable
from typing import Any, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, Field

from xtalent.core import Availability, ProfileRoot, Status
from xtalent.publish import PublishRecord

# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------


@runtime_checkable
class Embedder(Protocol):
    """Text → vector. Implementations must return a fixed-dimension vector."""

    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbedder:
    """Deterministic, offline embedder for tests and demos.

    Hashes the input to seed a PRNG and draws a unit-norm vector. Similar
    inputs produce unrelated vectors — this is **not** a real semantic
    embedder. Its job is to let the rest of the pipeline run end-to-end
    without a network.
    """

    def __init__(self, dimension: int = 384) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self._dim)
        vec /= np.linalg.norm(vec) or 1.0
        return [float(x) for x in vec]


class GrokEmbedder:
    """Stub adapter for xAI's embedding surface.

    Shape is intentional: a production implementation constructs an HTTP client
    at init and calls the provider's embeddings endpoint inside :meth:`embed`.
    Until the target endpoint is stable, calling :meth:`embed` raises
    :class:`NotImplementedError` so integrators catch the stub explicitly
    rather than silently degrading.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "grok-embed-1",
        base_url: str = "https://api.x.ai/v1",
        dimension: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:  # pragma: no cover - stub
        raise NotImplementedError(
            "GrokEmbedder is a stub. Wire up the xAI embeddings endpoint at "
            f"{self._base_url} using model={self._model!r} and return the vector."
        )


# ---------------------------------------------------------------------------
# Vector index
# ---------------------------------------------------------------------------


SearchPredicate = Callable[[dict[str, Any]], bool]
"""Applied to a candidate's metadata dict; return True to keep the hit."""


@runtime_checkable
class VectorIndex(Protocol):
    """Upsert/delete/search over (id, vector, metadata) tuples."""

    def upsert(self, id: str, vector: list[float], metadata: dict[str, Any]) -> None: ...

    def delete(self, id: str) -> None: ...

    def search(
        self,
        vector: list[float],
        k: int,
        predicate: SearchPredicate | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]: ...


class InMemoryVectorIndex:
    """Cosine-similarity KNN over an in-memory store.

    Fine up to a few thousand entries. Swap for Qdrant/pgvector at scale.
    """

    def __init__(self) -> None:
        self._vectors: dict[str, np.ndarray] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def upsert(self, id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        v = np.asarray(vector, dtype=float)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        self._vectors[id] = v
        self._metadata[id] = metadata

    def delete(self, id: str) -> None:
        self._vectors.pop(id, None)
        self._metadata.pop(id, None)

    def search(
        self,
        vector: list[float],
        k: int,
        predicate: SearchPredicate | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        if not self._vectors:
            return []
        q = np.asarray(vector, dtype=float)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        scored: list[tuple[str, float, dict[str, Any]]] = []
        for vid, v in self._vectors.items():
            meta = self._metadata[vid]
            if predicate is not None and not predicate(meta):
                continue
            score = float(np.dot(q, v))
            if math.isnan(score):
                continue
            scored.append((vid, score, meta))

        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]


# ---------------------------------------------------------------------------
# Public search API
# ---------------------------------------------------------------------------


class SearchFilters(BaseModel):
    """Structured filters applied before vector scoring."""

    model_config = {"extra": "forbid"}

    status: list[Status] | None = None
    availability: list[Availability] | None = None
    min_freshness: int | None = Field(default=None, ge=0, le=100)
    include_tombstoned: bool = False


class IndexedRecord(BaseModel):
    """The shape stored alongside each vector in the index."""

    model_config = {"frozen": True}

    profile_root: ProfileRoot
    cid: str


class SearchHit(BaseModel):
    model_config = {"frozen": True}

    score: float
    record: IndexedRecord


class TalentSearchIndex:
    """High-level semantic search over profile roots.

    Responsibilities:

    * turn a :class:`PublishRecord` into the text an embedder should see;
    * push the resulting vector and metadata into a :class:`VectorIndex`;
    * translate a natural-language query + filters into a KNN call.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        index: VectorIndex | None = None,
    ) -> None:
        self._embedder = embedder or DeterministicEmbedder()
        self._index = index or InMemoryVectorIndex()
        self._records: dict[str, IndexedRecord] = {}

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert(self, record: PublishRecord) -> None:
        """Index a freshly published CV.

        Tombstoned roots are removed from the index automatically.
        """
        handle = record.profile_root.handle
        if record.profile_root.tombstoned:
            self.delete(handle)
            return

        indexed = IndexedRecord(profile_root=record.profile_root, cid=record.cid)
        text = self._record_to_text(record)
        vector = self._embedder.embed(text)
        self._index.upsert(handle, vector, {"indexed": indexed})
        self._records[handle] = indexed

    def upsert_many(self, records: Iterable[PublishRecord]) -> None:
        for record in records:
            self.upsert(record)

    def delete(self, handle: str) -> None:
        self._index.delete(handle)
        self._records.pop(handle, None)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 10,
        filters: SearchFilters | None = None,
    ) -> list[SearchHit]:
        if k <= 0:
            return []
        vector = self._embedder.embed(query)
        predicate = _filters_predicate(filters)
        raw = self._index.search(vector, k=k, predicate=predicate)
        return [SearchHit(score=score, record=meta["indexed"]) for _, score, meta in raw]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_text(record: PublishRecord) -> str:
        """Project a record onto the text that will be embedded.

        We embed a dense summary rather than the raw Markdown so short,
        structured signals (title, skills, location) dominate the vector.
        """
        cv = _cv_from_markdown(record.cv_markdown)
        skills = ", ".join(
            f"{s.get('name')} ({s.get('level', '')})".strip(" ()")
            for s in cv.skills_matrix
            if s.get("name")
        )
        locations = ", ".join(cv.location_prefs)
        parts = [
            f"{cv.full_name} — {cv.title}",
            cv.summary,
            f"Skills: {skills}" if skills else "",
            f"Locations: {locations}" if locations else "",
            f"Status: {cv.status.value} / Availability: {cv.availability.value}",
            cv.experience,
            cv.projects,
        ]
        return "\n\n".join(p.strip() for p in parts if p.strip())


def _cv_from_markdown(markdown: str) -> Any:
    # Local import avoids a circular import at module load.
    from xtalent.core import XTalentCV

    return XTalentCV.from_markdown(markdown)


def _filters_predicate(filters: SearchFilters | None) -> SearchPredicate:
    if filters is None:
        def allow_all(_: dict[str, Any]) -> bool:
            return True
        return allow_all

    def check(meta: dict[str, Any]) -> bool:
        indexed: IndexedRecord = meta["indexed"]
        root = indexed.profile_root
        if not filters.include_tombstoned and root.tombstoned:
            return False
        if filters.status is not None and root.status not in filters.status:
            return False
        if filters.availability is not None and root.availability not in filters.availability:
            return False
        if filters.min_freshness is not None and root.freshness_score < filters.min_freshness:  # noqa: SIM103
            return False
        return True

    return check
