"""Publish a CV to the xTalent Graph reference publisher.

This is the 30-second, zero-setup demo: no Docker, no daemon, no keys.
It builds a realistic :class:`XTalentCV`, pins it through the
:class:`InMemoryIPFS` adapter (which produces a deterministic,
CIDv1-shaped mock CID), and prints a compact summary so you can see
exactly what the protocol produces.

When you are ready to publish for real, swap one line:

    from xtalent.publish import InMemoryIPFS            # ← replace
    from xtalent.backends.kubo import KuboIPFS          # ← with this
    publisher = TalentPublisher(ipfs=KuboIPFS())        # pins on a real Kubo node

Run the demo (from the ``python/`` directory)::

    pip install -e ".[dev]"
    python -m examples.publish_demo

No network calls are made. Output lands on stdout.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from xtalent import (
    Availability,
    InMemoryIPFS,
    Status,
    TalentPublisher,
    XTalentCV,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Well-known public IPFS gateway. The URL we print is *simulated* here —
#: the CID only lives in the process memory — but the same bytes pinned
#: via :class:`KuboIPFS` would resolve at this URL for real.
PUBLIC_GATEWAY = "https://ipfs.io/ipfs/{cid}"

logger = logging.getLogger("xtalent.examples.publish_demo")


# ---------------------------------------------------------------------------
# Sample CV
# ---------------------------------------------------------------------------


def build_cv() -> XTalentCV:
    """Return a small but realistic CV for the demo.

    Every field is validated by the Pydantic model, so typos fail fast.
    Edit freely when you want to publish your own.
    """
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.now(UTC),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=97,
        location_prefs=["remote", "Amsterdam", "EU"],
        skills_matrix=[
            {"name": "python", "years": 12, "level": "expert"},
            {"name": "llm-orchestration", "years": 3, "level": "advanced"},
            {"name": "retrieval-augmented-generation", "years": 3, "level": "advanced"},
            {"name": "typescript", "years": 7, "level": "advanced"},
            {"name": "vector-databases", "years": 2, "level": "advanced"},
            {"name": "ipfs", "years": 1, "level": "intermediate"},
        ],
        ai_twin_enabled=True,
        privacy={"contact": {"handle": "@tool_rate"}, "discoverable": True},
        full_name="Petrus Giesbers",
        title="AI developer — LLM systems, agent orchestration, applied ML",
        summary=(
            "Ships LLM-powered products end to end: prompt design, agent "
            "orchestration, retrieval, and evaluation. Cares about open "
            "protocols that put agents and humans on the same footing — "
            "which is why this CV lives on xTalent Graph."
        ),
        experience=(
            "- 2024–now: Building xTalent Graph — an open, LLM-native talent "
            "protocol with immutable CVs on IPFS, signed profile roots, and "
            "Qdrant semantic search.\n"
            "- 2020–2024: Lead AI developer across product teams — retrieval "
            "pipelines, eval harnesses, agent prototypes.\n"
            "- 2015–2020: Full-stack engineer — TypeScript services and data "
            "pipelines."
        ),
        projects=(
            "- xtalent-graph: open talent protocol (this repo).\n"
            "- Various LLM agent prototypes exploring tool-use, retrieval, "
            "and long-horizon planning."
        ),
    )


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def _preview(markdown: str, head: int = 15, tail: int = 10) -> str:
    """Return the first ``head`` and last ``tail`` lines, with an elision marker.

    If the document is short enough (``<= head + tail`` lines), returns
    the whole thing untouched.
    """
    lines = markdown.splitlines()
    if len(lines) <= head + tail:
        return "\n".join(lines)
    elided = len(lines) - head - tail
    head_block = "\n".join(lines[:head])
    tail_block = "\n".join(lines[-tail:])
    return f"{head_block}\n    … ({elided} lines elided) …\n{tail_block}"


def _print_summary(cid: str, handle: str, version: int, markdown: str) -> None:
    """Emit the final user-facing output block.

    We deliberately use :func:`print` here rather than :mod:`logging`:
    this is the *result* of the demo, not a progress signal, and it
    should be readable verbatim on stdout.
    """
    bar = "═" * 72
    print(f"\n{bar}")
    print("  Published (InMemoryIPFS — swap in KuboIPFS for real pinning)")
    print(bar)
    print(f"  handle          : {handle}")
    print(f"  version         : v{version}")
    print(f"  cid             : {cid}")
    print(f"  simulated url   : {PUBLIC_GATEWAY.format(cid=cid)}")
    print("                    (will resolve for real once pinned via Kubo)")
    print(bar)
    print("\n  Markdown (head + tail preview):\n")
    for line in _preview(markdown).splitlines():
        print(f"    {line}")
    print(f"\n{bar}")
    print("  Run yourself:  python -m examples.publish_demo")
    print(f"{bar}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )

    logger.info("building CV for @tool_rate (v1)")
    cv = build_cv()

    # InMemoryIPFS is fine for demos and tests. For real pinning, replace
    # this with `KuboIPFS()` (install with `pip install "xtalent[kubo]"`
    # and start a daemon via `docker compose -f docker-compose.dev.yml up`).
    logger.info("initializing TalentPublisher with InMemoryIPFS")
    publisher = TalentPublisher(ipfs=InMemoryIPFS())

    logger.info("publishing CV — serializes to Markdown, mock-pins, returns a CID")
    record = publisher.publish(cv)
    logger.info("done: cid=%s", record.cid)

    _print_summary(
        cid=record.cid,
        handle=record.profile_root.handle,
        version=record.profile_root.version,
        markdown=record.cv_markdown,
    )


if __name__ == "__main__":
    main()
