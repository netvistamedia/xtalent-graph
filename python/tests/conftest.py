"""Shared fixtures for xtalent tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtalent import (
    Availability,
    InMemoryIPFS,
    Status,
    TalentPublisher,
    TalentSearchIndex,
    XTalentCV,
)


@pytest.fixture
def sample_cv() -> XTalentCV:
    return XTalentCV(
        handle="@ada",
        version=1,
        last_updated=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=96,
        salary_expectation={"currency": "EUR", "min": 120000, "max": 160000},
        location_prefs=["remote", "Amsterdam"],
        skills_matrix=[
            {"name": "rust", "years": 6, "level": "expert"},
            {"name": "distributed-systems", "years": 5, "level": "expert"},
        ],
        ai_twin_enabled=True,
        privacy={"contact": {"handle": "@ada"}, "discoverable": True},
        full_name="Ada Lovelace",
        title="Staff software engineer, distributed systems",
        summary="Builds consensus-heavy systems. Cares about correctness under partition.",
        experience="- 2022–now: Principal at Nimbus (distributed log).\n- 2018–2022: Staff at Orbit.",
        projects="- rustraft: a teaching raft implementation.\n- obs-kit: OpenTelemetry patterns.",
        endorsements="_Peer-reviewed on rustraft by @alan._",
    )


@pytest.fixture
def publisher() -> TalentPublisher:
    return TalentPublisher(ipfs=InMemoryIPFS())


@pytest.fixture
def index() -> TalentSearchIndex:
    return TalentSearchIndex()
