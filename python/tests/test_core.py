"""Tests for xtalent.core — the protocol's data contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from xtalent import Availability, Status, XTalentCV


def test_handle_must_match_pattern() -> None:
    with pytest.raises(ValidationError):
        XTalentCV(
            handle="ada",  # missing leading @
            full_name="Ada",
            title="Engineer",
            summary="s",
            experience="e",
            projects="p",
        )


def test_freshness_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        XTalentCV(
            handle="@ada",
            freshness_score=101,
            full_name="Ada",
            title="Engineer",
            summary="s",
            experience="e",
            projects="p",
        )


def test_next_available_requires_date() -> None:
    with pytest.raises(ValidationError) as exc:
        XTalentCV(
            handle="@ada",
            availability=Availability.NEXT_AVAILABLE,
            full_name="Ada",
            title="Engineer",
            summary="s",
            experience="e",
            projects="p",
        )
    assert "next_available_date" in str(exc.value)


def test_markdown_roundtrip_is_byte_identical(sample_cv: XTalentCV) -> None:
    first = sample_cv.to_markdown()
    parsed = XTalentCV.from_markdown(first)
    second = parsed.to_markdown()
    assert first == second, "serialize → parse → serialize must be stable"


def test_markdown_contains_required_sections(sample_cv: XTalentCV) -> None:
    md = sample_cv.to_markdown()
    for section in ("## Summary", "## Experience", "## Projects"):
        assert section in md


def test_from_markdown_rejects_missing_frontmatter() -> None:
    with pytest.raises(ValueError, match="frontmatter"):
        XTalentCV.from_markdown("# No frontmatter here\n\n## Summary\n...\n")


def test_from_markdown_rejects_missing_section(sample_cv: XTalentCV) -> None:
    md = sample_cv.to_markdown().replace("## Projects", "## Hobbies")
    with pytest.raises(ValueError, match="Projects"):
        XTalentCV.from_markdown(md)


def test_to_profile_root_mirrors_cv(sample_cv: XTalentCV) -> None:
    root = sample_cv.to_profile_root(latest_cid="bafyfake")
    assert root.handle == sample_cv.handle
    assert root.latest_cid == "bafyfake"
    assert root.version == sample_cv.version
    assert root.status == sample_cv.status
    assert root.availability == sample_cv.availability
    assert root.freshness_score == sample_cv.freshness_score
    assert root.tombstoned is False


def test_status_and_availability_are_enums(sample_cv: XTalentCV) -> None:
    assert isinstance(sample_cv.status, Status)
    assert isinstance(sample_cv.availability, Availability)


def test_empty_full_name_rejected() -> None:
    with pytest.raises(ValidationError, match="full_name"):
        XTalentCV(
            handle="@ada",
            full_name="",
            title="Engineer",
            summary="s",
            experience="e",
            projects="p",
        )


def test_empty_title_rejected() -> None:
    with pytest.raises(ValidationError, match="title"):
        XTalentCV(
            handle="@ada",
            full_name="Ada",
            title="",
            summary="s",
            experience="e",
            projects="p",
        )
