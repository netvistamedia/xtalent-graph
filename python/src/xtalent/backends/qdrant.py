"""Qdrant implementation of :class:`xtalent.search.VectorIndex`.

Install the optional extra to use this backend::

    pip install "xtalent[qdrant]"

Usage — local in-process (great for tests and scripts)::

    from xtalent import TalentSearchIndex
    from xtalent.backends.qdrant import QdrantIndex

    index = TalentSearchIndex(index=QdrantIndex())  # :memory:

Usage — remote Qdrant::

    index = TalentSearchIndex(index=QdrantIndex(url="http://localhost:6333"))

Predicate semantics
-------------------
The :data:`~xtalent.search.SearchPredicate` protocol is a plain Python
callable over a metadata dict. It cannot be translated to Qdrant's native
``Filter`` language without knowing the caller's intent, so this adapter
**over-fetches** (``k * over_fetch``) and applies the predicate client-side.
Results are correct; they are not optimal when filters are highly selective.

For large-scale deployments with known filter shapes, read
:attr:`QdrantIndex.client` and issue native Qdrant ``Filter`` queries
directly — the reference adapter is deliberately small so you can build on
top of it.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

from xtalent.search import SearchPredicate

if TYPE_CHECKING:  # pragma: no cover - typing only
    from qdrant_client import QdrantClient

_QDRANT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace


def _handle_to_uuid(handle: str) -> str:
    """Map an ``@handle`` to a deterministic UUIDv5.

    Qdrant accepts only unsigned ints or UUID strings as point IDs. The
    handle is stored in the payload for round-tripping.
    """
    # uuid5 is deterministic and collision-resistant for our key space.
    # We keep sha256 as the actual namespace bytes for hygiene.
    digest = hashlib.sha256(handle.encode("utf-8")).digest()[:16]
    return str(uuid.UUID(bytes=digest, version=5))


class QdrantIndex:
    """:class:`~xtalent.search.VectorIndex` backed by a Qdrant collection."""

    def __init__(
        self,
        *,
        url: str | None = None,
        location: str = ":memory:",
        api_key: str | None = None,
        collection: str = "xtalent-profiles",
        dimension: int = 384,
        over_fetch: int = 5,
    ) -> None:
        """Create or connect to a Qdrant-backed index.

        Args:
            url: Full URL of a remote Qdrant instance (e.g. ``http://localhost:6333``).
                When set, ``location`` is ignored.
            location: Local/embedded location. ``":memory:"`` runs an
                in-process instance, handy for tests. Ignored when ``url`` is set.
            api_key: Optional API key for Qdrant Cloud.
            collection: Collection name. Auto-created on first use.
            dimension: Embedding dimension. Must match the active
                :class:`~xtalent.search.Embedder`.
            over_fetch: Multiplier applied to ``k`` when a client-side
                predicate is present; caps at 200.
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as exc:  # pragma: no cover - import-time guard
            raise ImportError(
                "qdrant-client is not installed. Install the optional extra: "
                "`pip install 'xtalent[qdrant]'`."
            ) from exc

        if url:
            self._client = QdrantClient(url=url, api_key=api_key)
        else:
            self._client = QdrantClient(location=location)

        self._collection = collection
        self._dimension = dimension
        self._over_fetch = max(1, over_fetch)

        existing = {c.name for c in self._client.get_collections().collections}
        if collection not in existing:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    @property
    def client(self) -> QdrantClient:
        """Exposed for callers who want to issue native Qdrant queries."""
        return self._client

    @property
    def collection_name(self) -> str:
        return self._collection

    # ------------------------------------------------------------------
    # VectorIndex protocol
    # ------------------------------------------------------------------

    def upsert(self, id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        from qdrant_client.models import PointStruct

        payload = _serialize_payload(id, metadata)
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(id=_handle_to_uuid(id), vector=vector, payload=payload),
            ],
        )

    def delete(self, id: str) -> None:
        from qdrant_client.models import PointIdsList

        self._client.delete(
            collection_name=self._collection,
            points_selector=PointIdsList(points=[_handle_to_uuid(id)]),
        )

    def search(
        self,
        vector: list[float],
        k: int,
        predicate: SearchPredicate | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        if k <= 0:
            return []
        limit = k if predicate is None else min(k * self._over_fetch, 200)
        response = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        out: list[tuple[str, float, dict[str, Any]]] = []
        for hit in response.points:
            handle, metadata = _deserialize_payload(hit.payload)
            if predicate is not None and not predicate(metadata):
                continue
            out.append((handle, float(hit.score), metadata))
            if len(out) >= k:
                break
        return out


# ---------------------------------------------------------------------------
# Payload (de)serialization
# ---------------------------------------------------------------------------


def _serialize_payload(handle: str, metadata: dict[str, Any]) -> dict[str, Any]:
    indexed = metadata["indexed"]
    # by_alias=True: our Pydantic models declare `schema` as an alias for
    # `schema_id`. Serializing by alias preserves round-trip validation.
    return {
        "handle": handle,
        "indexed": indexed.model_dump(mode="json", by_alias=True),
    }


def _deserialize_payload(payload: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    from xtalent.search import IndexedRecord

    if payload is None:
        return ("", {})
    handle = str(payload.get("handle", ""))
    indexed = IndexedRecord.model_validate(payload["indexed"])
    return handle, {"indexed": indexed}


__all__ = ["QdrantIndex"]
