"""End-to-end Python demo.

Runs without any network:
    python examples/demo.py

Publishes two CVs against the in-memory backends, indexes them, and prints
the top search hits for a sample query.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from xtalent import (
    Availability,
    InMemoryIPFS,
    SearchFilters,
    Status,
    TalentPublisher,
    TalentSearchIndex,
    XTalentCV,
)


def _ada() -> XTalentCV:
    return XTalentCV.from_markdown_file(
        Path(__file__).parent.parent / "schema" / "example-cv-v1.md"
    )


def _grace() -> XTalentCV:
    return XTalentCV(
        handle="@grace",
        version=1,
        last_updated=datetime(2026, 3, 1, tzinfo=timezone.utc),
        status=Status.PASSIVE,
        availability=Availability.NEXT_AVAILABLE,
        next_available_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        freshness_score=82,
        location_prefs=["remote", "Berlin"],
        skills_matrix=[
            {"name": "typescript", "years": 8, "level": "expert"},
            {"name": "graph-databases", "years": 5, "level": "advanced"},
        ],
        ai_twin_enabled=True,
        privacy={"contact": {"handle": "@grace"}, "discoverable": True},
        full_name="Grace Hopper",
        title="Principal engineer, compilers and graph systems",
        summary="Builds languages and the graphs that back them.",
        experience="- 2020–now: Principal at Edge.\n- 2015–2020: Staff at Thicket.",
        projects="- lispgraph: a tiny language for graph rewrites.",
    )


def main() -> None:
    publisher = TalentPublisher(ipfs=InMemoryIPFS())
    index = TalentSearchIndex()

    for cv in (_ada(), _grace()):
        record = publisher.publish(cv)
        index.upsert(record)
        print(f"published {cv.handle} → {record.cid}")

    print()
    print("search: 'staff engineer, distributed systems, rust'")
    hits = index.search(
        "staff engineer, distributed systems, rust",
        k=5,
        filters=SearchFilters(
            availability=[Availability.LOOKING, Availability.NEXT_AVAILABLE],
            min_freshness=50,
        ),
    )
    for hit in hits:
        root = hit.record.profile_root
        print(f"  {root.handle}  score={hit.score:+.3f}  v{root.version}  cid={hit.record.cid}")


if __name__ == "__main__":
    main()
