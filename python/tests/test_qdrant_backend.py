"""Tests for xtalent.backends.qdrant against an in-process Qdrant.

The tests skip gracefully if ``qdrant-client`` is not installed. They use
``QdrantClient(":memory:")``-backed collections so they run without a
server and without touching disk.
"""

from __future__ import annotations

import pytest

pytest.importorskip("qdrant_client")

from xtalent import (
    Availability,
    SearchFilters,
    Status,
    TalentPublisher,
    TalentSearchIndex,
    XTalentCV,
)
from xtalent.backends.qdrant import QdrantIndex


@pytest.fixture
def qdrant_index() -> TalentSearchIndex:
    backend = QdrantIndex(dimension=384, collection="xtalent-test")
    return TalentSearchIndex(index=backend)


def test_upsert_then_search_returns_hit(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    record = publisher.publish(sample_cv)
    qdrant_index.upsert(record)

    hits = qdrant_index.search("distributed systems", k=5)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.record.profile_root.handle == "@ada"
    assert hit.record.cid == record.cid


def test_status_filter_drops_closed(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    qdrant_index.upsert(publisher.publish(sample_cv))
    assert qdrant_index.search("x", k=5, filters=SearchFilters(status=[Status.CLOSED])) == []


def test_min_freshness_filter(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    qdrant_index.upsert(publisher.publish(sample_cv))
    assert qdrant_index.search("x", k=5, filters=SearchFilters(min_freshness=50))
    assert not qdrant_index.search("x", k=5, filters=SearchFilters(min_freshness=99))


def test_availability_filter(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    qdrant_index.upsert(publisher.publish(sample_cv))
    looking = SearchFilters(availability=[Availability.LOOKING])
    not_looking = SearchFilters(availability=[Availability.NOT_LOOKING])
    assert qdrant_index.search("x", k=5, filters=looking)
    assert not qdrant_index.search("x", k=5, filters=not_looking)


def test_delete_removes_from_index(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    qdrant_index.upsert(publisher.publish(sample_cv))
    assert qdrant_index.search("x", k=5)

    qdrant_index.delete("@ada")
    assert qdrant_index.search("x", k=5) == []


def test_k_zero_returns_empty(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    qdrant_index.upsert(publisher.publish(sample_cv))
    assert qdrant_index.search("x", k=0) == []


def test_upsert_is_idempotent_on_same_handle(
    publisher: TalentPublisher,
    qdrant_index: TalentSearchIndex,
    sample_cv: XTalentCV,
) -> None:
    """Publishing v1 then v2 must not produce two rows — the UUID derives from the handle."""
    qdrant_index.upsert(publisher.publish(sample_cv))
    v2 = sample_cv.model_copy(update={"version": 2, "freshness_score": 70})
    qdrant_index.upsert(publisher.publish(v2))

    hits = qdrant_index.search("anything", k=10)
    assert len(hits) == 1
    assert hits[0].record.profile_root.version == 2
    assert hits[0].record.profile_root.freshness_score == 70
