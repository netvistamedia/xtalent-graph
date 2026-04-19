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


def test_record_to_text_includes_canonical_skill_names(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    # sample_cv uses the canonical [{name, years, level}] shape per docs/schema.md.
    # _record_to_text pulls skill names into the embedding text; the demo must
    # use this shape or its CVs index with no skill signal.
    record = publisher.publish(sample_cv)
    text = TalentSearchIndex._record_to_text(record)
    assert "rust" in text
    assert "distributed-systems" in text


def test_demo_cv_uses_canonical_skills_shape() -> None:
    # Regression guard for the examples/publish_demo.py demo: each
    # skills_matrix entry must carry a `name` key, otherwise _record_to_text
    # drops it and semantic search over the demo CV loses its skill signal.
    import importlib.util
    import pathlib

    demo_path = pathlib.Path(__file__).parent.parent / "examples" / "publish_demo.py"
    spec = importlib.util.spec_from_file_location("_publish_demo_for_test", demo_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cv = module.build_demo_cv()
    assert cv.skills_matrix, "demo should publish with a non-empty skills_matrix"
    for entry in cv.skills_matrix:
        assert "name" in entry, (
            f"demo skill entry {entry!r} is missing 'name' — it won't appear "
            f"in the search embedding (see search.py::_record_to_text)"
        )
