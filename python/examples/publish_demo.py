# One-line swap to KuboIPFS when ready:
#   from xtalent.backends.kubo import KuboIPFS
#   publisher = TalentPublisher(ipfs=KuboIPFS())
"""Publish an idea-stage XTalentCV through the reference pipeline.

Zero-setup demo: no Docker, no daemon, no keys. Builds a realistic CV for
``@tool_rate`` (Petrus Giesbers — AI developer, idea-stage), pins it
through :class:`InMemoryIPFS` (a deterministic, CIDv1-shaped mock), and
prints four things you actually want to see:

1. head + tail of the generated Markdown;
2. the CID the publisher returned;
3. a *simulated* canonical profile URL (what the xTalent frontend would
   surface for this handle);
4. a real IPFS gateway link — if you swap :class:`InMemoryIPFS` for
   :class:`KuboIPFS`, the same CID resolves at that URL for real.

Run from the ``python/`` directory::

    pip install -e ".[dev]"
    python -m examples.publish_demo
"""

from __future__ import annotations

from datetime import UTC, datetime

from xtalent import (
    Availability,
    InMemoryIPFS,
    Status,
    TalentPublisher,
    XTalentCV,
)

#: Public IPFS gateway template. The bytes we pin here live only in
#: process memory, but the *same* bytes pinned through KuboIPFS resolve
#: at this URL for real.
PUBLIC_GATEWAY = "https://ipfs.io/ipfs/{cid}"

#: Simulated canonical profile URL — the human-readable home that the
#: xTalent Graph frontend would surface for a published handle.
SIMULATED_PROFILE_URL = "https://xtalent.graph/{handle}"


# ---------------------------------------------------------------------------
# Sample CV — idea-stage AI developer
# ---------------------------------------------------------------------------


def build_cv() -> XTalentCV:
    """Realistic, idea-stage CV for ``@tool_rate`` (Petrus Giesbers).

    "Idea-stage" in the sense that the headline is the current venture
    (xTalent Graph), not a decade of prior roles. Prior experience is
    framed as background, not the product.
    """
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.now(UTC),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=95,
        location_prefs=["remote", "Amsterdam", "EU"],
        skills_matrix=[
            {"name": "python", "years": 10, "level": "expert"},
            {"name": "llm-orchestration", "years": 2, "level": "advanced"},
            {"name": "retrieval-augmented-generation", "years": 2, "level": "advanced"},
            {"name": "pydantic", "years": 4, "level": "advanced"},
            {"name": "ipfs", "years": 1, "level": "intermediate"},
            {"name": "protocol-design", "years": 1, "level": "intermediate"},
        ],
        ai_twin_enabled=True,
        privacy={"contact": {"handle": "@tool_rate"}, "discoverable": True},
        full_name="Petrus Giesbers",
        title="AI developer — idea-stage, building xTalent Graph",
        summary=(
            "Idea-stage founder-engineer prototyping xTalent Graph: an open, "
            "LLM-native talent protocol. Currently shipping the Python "
            "reference implementation — immutable CVs on IPFS, signed "
            "profile roots, semantic search over Qdrant. Looking for early "
            "collaborators, design partners, and sharp critique."
        ),
        experience=(
            "- 2026–now: Founder / solo engineer on xTalent Graph. Writing "
            "the protocol spec, the Python reference publisher, and the "
            "first real CVs that run through it end-to-end.\n"
            "- Prior: a decade of Python and applied ML across product "
            "teams — retrieval pipelines, evaluation harnesses, agent "
            "prototypes. Deliberately kept as background here: the idea "
            "is the product right now."
        ),
        projects=(
            "- xtalent-graph (this repo): open talent protocol + Python "
            "reference implementation. InMemoryIPFS today, KuboIPFS next.\n"
            "- Small agent prototypes feeding the protocol's design: what "
            "does an AI recruiter actually need to read in a CV?"
        ),
    )


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def _preview(markdown: str, head: int = 12, tail: int = 8) -> str:
    """Return the first ``head`` and last ``tail`` lines, joined by an elision marker.

    Short documents (``<= head + tail`` lines) are returned whole.
    """
    lines = markdown.splitlines()
    if len(lines) <= head + tail:
        return "\n".join(lines)
    elided = len(lines) - head - tail
    head_block = "\n".join(lines[:head])
    tail_block = "\n".join(lines[-tail:])
    return f"{head_block}\n    … ({elided} lines elided) …\n{tail_block}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cv = build_cv()

    # Swap InMemoryIPFS → KuboIPFS to pin against a real node.
    publisher = TalentPublisher(ipfs=InMemoryIPFS())
    record = publisher.publish(cv)

    cid = record.cid
    handle = record.profile_root.handle
    simulated_url = SIMULATED_PROFILE_URL.format(handle=handle.lstrip("@"))
    gateway_url = PUBLIC_GATEWAY.format(cid=cid)

    bar = "═" * 72
    print(f"\n{bar}")
    print("  xTalent Graph — publish_demo")
    print("  backend: InMemoryIPFS   (one-line swap → KuboIPFS when ready)")
    print(bar)
    print(f"  handle          : {handle}")
    print(f"  version         : v{record.profile_root.version}")
    print(f"  cid             : {cid}")
    print(f"  simulated url   : {simulated_url}")
    print(f"  ipfs gateway    : {gateway_url}")
    print(bar)

    print("\n  Markdown (head + tail preview):\n")
    for line in _preview(record.cv_markdown).splitlines():
        print(f"    {line}")
    print(f"\n{bar}\n")


if __name__ == "__main__":
    main()
