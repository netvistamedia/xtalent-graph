"""Tests for xtalent.publish — the write path."""

from __future__ import annotations

import pytest

from xtalent import PublishError, TalentPublisher, XTalentCV


def test_publish_pins_and_creates_root(publisher: TalentPublisher, sample_cv: XTalentCV) -> None:
    record = publisher.publish(sample_cv)

    assert record.cid.startswith("bafy")
    assert record.profile_root.handle == "@ada"
    assert record.profile_root.latest_cid == record.cid
    assert record.profile_root.version == 1
    assert publisher.get_root("@ada") == record.profile_root


def test_publish_is_content_addressed(publisher: TalentPublisher, sample_cv: XTalentCV) -> None:
    record = publisher.publish(sample_cv)
    fetched = publisher.get_cv(record.cid)
    assert fetched.handle == sample_cv.handle
    assert fetched.to_markdown() == record.cv_markdown


def test_republish_must_bump_version(publisher: TalentPublisher, sample_cv: XTalentCV) -> None:
    publisher.publish(sample_cv)
    # Same version → refused.
    with pytest.raises(PublishError, match="strictly greater"):
        publisher.publish(sample_cv)


def test_new_version_supersedes_old(publisher: TalentPublisher, sample_cv: XTalentCV) -> None:
    publisher.publish(sample_cv)
    v2 = sample_cv.model_copy(update={"version": 2, "freshness_score": 80})
    record = publisher.publish(v2)

    root = publisher.get_root("@ada")
    assert root is not None
    assert root.version == 2
    assert root.latest_cid == record.cid
    assert root.freshness_score == 80


def test_tombstone_blocks_future_publishes(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    publisher.publish(sample_cv)
    publisher.tombstone("@ada", reason="GDPR request")

    v2 = sample_cv.model_copy(update={"version": 2})
    with pytest.raises(PublishError, match="tombstoned"):
        publisher.publish(v2)


def test_tombstone_unknown_handle_raises(publisher: TalentPublisher) -> None:
    with pytest.raises(PublishError, match="unknown handle"):
        publisher.tombstone("@ghost")


def test_handle_without_at_is_accepted_on_read(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    publisher.publish(sample_cv)
    assert publisher.get_root("ada") == publisher.get_root("@ada")
