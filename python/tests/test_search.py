"""Tests for xtalent.search — indexing and query semantics."""

from __future__ import annotations

from xtalent import (
    Availability,
    SearchFilters,
    Status,
    TalentPublisher,
    TalentSearchIndex,
    XTalentCV,
)


def test_upsert_then_search_returns_hit(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)

    hits = index.search("distributed systems", k=5)
    assert len(hits) == 1
    assert hits[0].record.profile_root.handle == "@ada"
    assert hits[0].record.cid == record.cid


def test_filters_drop_closed_profiles(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)

    filters = SearchFilters(status=[Status.CLOSED])
    assert index.search("anything", k=5, filters=filters) == []


def test_filters_min_freshness(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)

    assert index.search("x", k=5, filters=SearchFilters(min_freshness=50))
    assert not index.search("x", k=5, filters=SearchFilters(min_freshness=99))


def test_tombstone_removes_from_index(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)
    assert index.search("x", k=5)

    publisher.tombstone("@ada")
    index.delete("@ada")
    assert index.search("x", k=5) == []


def test_availability_filter(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)

    looking = SearchFilters(availability=[Availability.LOOKING])
    not_looking = SearchFilters(availability=[Availability.NOT_LOOKING])
    assert index.search("x", k=5, filters=looking)
    assert not index.search("x", k=5, filters=not_looking)


def test_k_zero_returns_empty(
    publisher: TalentPublisher, index: TalentSearchIndex, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    index.upsert(record)
    assert index.search("x", k=0) == []
