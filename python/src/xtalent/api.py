"""FastAPI reference server for xTalent Graph.

This module wires together the core models, the publisher, and the search
index into a small HTTP surface described in ``docs/api.md``. It is a
*reference* server: production deployments are expected to replace the
in-memory backends via dependency overrides.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from xtalent.core import ProfileRoot, XTalentCV
from xtalent.publish import InMemoryIPFS, PublishError, TalentPublisher
from xtalent.search import SearchFilters, SearchHit, TalentSearchIndex

logger = logging.getLogger("xtalent.api")

# ---------------------------------------------------------------------------
# Shared state (reference implementation — swap in production)
# ---------------------------------------------------------------------------


_TRUTHY = frozenset({"1", "true", "t", "yes", "y", "on"})


def _envflag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def _build_index() -> TalentSearchIndex:
    """Construct the reference search index.

    Environment:

    * ``XTALENT_QDRANT_URL`` — when set, wires the Qdrant backend
      (requires ``pip install 'xtalent[qdrant]'``).
      ``XTALENT_QDRANT_COLLECTION`` / ``XTALENT_QDRANT_API_KEY`` are honored.
    * ``XTALENT_REQUIRE_SIGNATURES`` — when truthy, the index fail-closes
      on unsigned or invalid-signature profile roots.
    """
    require_signatures = _envflag("XTALENT_REQUIRE_SIGNATURES")
    if require_signatures:
        logger.info("signature verification required on upsert")

    url = os.getenv("XTALENT_QDRANT_URL")
    if not url:
        return TalentSearchIndex(require_signatures=require_signatures)

    try:
        from xtalent.backends.qdrant import QdrantIndex
    except ImportError:
        logger.warning(
            "XTALENT_QDRANT_URL is set but qdrant-client is not installed; "
            "falling back to in-memory index. Install: pip install 'xtalent[qdrant]'."
        )
        return TalentSearchIndex(require_signatures=require_signatures)

    collection = os.getenv("XTALENT_QDRANT_COLLECTION", "xtalent-profiles")
    api_key = os.getenv("XTALENT_QDRANT_API_KEY")
    logger.info("using Qdrant backend at %s (collection=%s)", url, collection)
    return TalentSearchIndex(
        index=QdrantIndex(url=url, api_key=api_key, collection=collection),
        require_signatures=require_signatures,
    )


_ipfs = InMemoryIPFS()
_publisher = TalentPublisher(ipfs=_ipfs)
_index = _build_index()


def get_publisher() -> TalentPublisher:
    return _publisher


def get_index() -> TalentSearchIndex:
    return _index


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PublishRequest(BaseModel):
    cv_markdown: str = Field(min_length=1)


class PublishResponse(BaseModel):
    handle: str
    cid: str
    profile_root: ProfileRoot


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=10, ge=1, le=100)
    filters: SearchFilters | None = None


class SearchResponse(BaseModel):
    hits: list[SearchHit]


class TombstoneRequest(BaseModel):
    reason: str | None = None


class TombstoneResponse(BaseModel):
    handle: str
    tombstoned: bool


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


app = FastAPI(
    title="xTalent Graph",
    version="0.1.0",
    summary="Open, LLM-native talent protocol.",
    description=(
        "Reference HTTP surface. See `docs/api.md` for the authoritative spec "
        "and `docs/schema.md` for the data contracts."
    ),
)


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


@app.post("/publish", response_model=PublishResponse)
def publish(
    req: PublishRequest,
    publisher: TalentPublisher = Depends(get_publisher),
    index: TalentSearchIndex = Depends(get_index),
) -> PublishResponse:
    # The reference `/publish` produces an unsigned profile root server-side.
    # A signed-publish HTTP flow (client-computed signature + canonical
    # `updated_at`) is tracked as a v0.2 API design item — until then, use
    # the library API (`xtalent.signing` + `TalentSearchIndex.upsert`) in
    # deployments that enforce signatures.
    if index.require_signatures:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail=_error(
                "signed_publish_not_implemented",
                "this server requires signatures, but HTTP signed publish is "
                "not yet implemented. Use the Python library API "
                "(xtalent.signing + TalentSearchIndex.upsert) directly.",
            ),
        )
    try:
        cv = XTalentCV.from_markdown(req.cv_markdown)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_error("invalid_request", str(exc)),
        ) from exc

    try:
        record = publisher.publish(cv)
    except PublishError as exc:
        code = "tombstoned" if "tombstoned" in str(exc) else "conflict"
        http_status = (
            status.HTTP_410_GONE if code == "tombstoned" else status.HTTP_409_CONFLICT
        )
        raise HTTPException(http_status, detail=_error(code, str(exc))) from exc

    index.upsert(record)
    return PublishResponse(handle=cv.handle, cid=record.cid, profile_root=record.profile_root)


@app.get("/profile/{handle}", response_model=ProfileRoot)
def get_profile(
    handle: str,
    publisher: TalentPublisher = Depends(get_publisher),
) -> ProfileRoot:
    root = publisher.get_root(handle)
    if root is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=_error("not_found", f"unknown handle: {handle}"),
        )
    return root


@app.get("/cv/{cid}")
def get_cv(
    cid: str,
    publisher: TalentPublisher = Depends(get_publisher),
) -> Response:
    try:
        markdown = publisher.get_cv_markdown(cid)
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=_error("not_found", f"cid not pinned: {cid}"),
        ) from exc
    return Response(content=markdown, media_type="text/markdown; charset=utf-8")


@app.post("/search", response_model=SearchResponse)
def search(
    req: SearchRequest,
    index: TalentSearchIndex = Depends(get_index),
) -> SearchResponse:
    hits = index.search(req.query, k=req.k, filters=req.filters)
    return SearchResponse(hits=hits)


@app.delete("/profile/{handle}", response_model=TombstoneResponse)
def delete_profile(
    handle: str,
    req: TombstoneRequest | None = Body(default=None),
    publisher: TalentPublisher = Depends(get_publisher),
    index: TalentSearchIndex = Depends(get_index),
) -> TombstoneResponse:
    try:
        root = publisher.tombstone(handle, reason=(req.reason if req else None))
    except PublishError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=_error("not_found", str(exc)),
        ) from exc
    index.delete(root.handle)
    return TombstoneResponse(handle=root.handle, tombstoned=root.tombstoned)
