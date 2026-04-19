"""Publish a real CV to IPFS in ~30 seconds.

What this script does, end to end:

1. Builds a small but realistic :class:`XTalentCV` in memory.
2. Connects to a local Kubo IPFS node via :class:`KuboIPFS`.
3. Serializes the CV to canonical Markdown and pins it (real CID, really
   pinned).
4. Prints a compact summary: the CID, a local gateway URL, a public
   gateway URL, and a head/tail preview of the pinned Markdown.

Prereqs (one-time):

    # From the repo root — starts Kubo on :5001 and its gateway on :8080.
    docker compose -f docker-compose.dev.yml up -d

    # From python/ — install the package with the Kubo extra.
    pip install -e ".[kubo]"

Run the demo (from the ``python/`` directory):

    python -m examples.publish_demo

If Kubo is not reachable the script exits non-zero with a message
pointing at the docker-compose command above.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

from xtalent import (
    Availability,
    Status,
    TalentPublisher,
    XTalentCV,
    build_ipfs_client,
)
from xtalent.backends.kubo import KuboConnectionError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Default Kubo HTTP API. Override by editing or by swapping in the env-var
#: variant from xtalent.api if you're wiring this into a server.
KUBO_URL = "http://127.0.0.1:5001"

#: Local read-only gateway exposed by the ipfs/kubo image in
#: docker-compose.dev.yml.
LOCAL_GATEWAY = "http://127.0.0.1:8080/ipfs/{cid}"

#: A well-known public IPFS gateway for quick inspection from anywhere.
#: Propagation takes a moment after the first pin.
PUBLIC_GATEWAY = "https://ipfs.io/ipfs/{cid}"

logger = logging.getLogger("xtalent.examples.publish_demo")


# ---------------------------------------------------------------------------
# Sample CV
# ---------------------------------------------------------------------------


def build_sample_cv() -> XTalentCV:
    """Return a small, realistic CV suitable for the 30-second demo.

    Edit the fields below when you want to publish your own CV — every
    attribute is validated by the Pydantic model, so typos fail fast.
    """
    return XTalentCV(
        handle="@demo",
        version=1,
        last_updated=datetime.now(UTC),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=95,
        location_prefs=["remote", "Amsterdam", "Berlin"],
        skills_matrix=[
            {"name": "python", "years": 10, "level": "expert"},
            {"name": "distributed-systems", "years": 6, "level": "advanced"},
            {"name": "llm-orchestration", "years": 2, "level": "intermediate"},
            {"name": "ipfs", "years": 1, "level": "intermediate"},
        ],
        ai_twin_enabled=True,
        privacy={"contact": {"handle": "@demo"}, "discoverable": True},
        full_name="Demo User",
        title="Staff engineer, distributed systems & LLM infrastructure",
        summary=(
            "Builds large-scale search and orchestration systems. Loves open "
            "protocols, dislikes walled gardens. This CV is published on "
            "xTalent Graph — pinned on IPFS and signable with Ed25519."
        ),
        experience=(
            "- 2023–now: Staff Engineer at Contoso — shipped a 20-node "
            "consensus cluster that halved ingestion latency.\n"
            "- 2019–2023: Senior Engineer at Acme — rewrote the ingestion "
            "tier in Rust; 6× memory reduction.\n"
            "- 2015–2019: Software Engineer at Initech — built the first "
            "internal search over 40M documents."
        ),
        projects=(
            "- rustraft: teaching Raft implementation with property-based "
            "tests over a simulated network.\n"
            "- xtalent-graph: open, LLM-native talent protocol with real "
            "IPFS, signed profile roots, and Qdrant semantic search."
        ),
    )


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def _preview(markdown: str, head: int = 15, tail: int = 10) -> str:
    """Return the first ``head`` and last ``tail`` lines of ``markdown``.

    If the document is short enough (``<= head + tail`` lines), returns the
    whole thing untouched.
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

    We deliberately use ``print`` here rather than :mod:`logging`: this is
    the *result* of the demo, not a progress signal, and it should be
    readable verbatim on stdout.
    """
    bar = "═" * 72
    print(f"\n{bar}")
    print("  Published to IPFS")
    print(bar)
    print(f"  handle         : {handle}")
    print(f"  version        : v{version}")
    print(f"  cid            : {cid}")
    print(f"  local gateway  : {LOCAL_GATEWAY.format(cid=cid)}")
    print(f"  public gateway : {PUBLIC_GATEWAY.format(cid=cid)}")
    print(bar)
    print("\n  Markdown (preview):\n")
    for line in _preview(markdown).splitlines():
        print(f"    {line}")
    print(f"\n{bar}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )

    logger.info("building sample CV (@demo, v1)")
    cv = build_sample_cv()

    logger.info("connecting to Kubo at %s", KUBO_URL)
    # build_ipfs_client("kubo", url=...) returns a KuboIPFS — the factory
    # is handy when the mode comes from config (env vars, YAML, CLI args).
    ipfs = build_ipfs_client("kubo", url=KUBO_URL)
    publisher = TalentPublisher(ipfs=ipfs)

    logger.info("pinning CV to IPFS — this is the only network call")
    try:
        record = publisher.publish(cv)
    except KuboConnectionError as exc:
        logger.error("kubo unreachable: %s", exc)
        logger.error(
            "start the dev stack from the repo root:\n"
            "    docker compose -f docker-compose.dev.yml up -d"
        )
        sys.exit(1)

    logger.info("published: cid=%s", record.cid)
    _print_summary(
        cid=record.cid,
        handle=record.profile_root.handle,
        version=record.profile_root.version,
        markdown=record.cv_markdown,
    )


if __name__ == "__main__":
    main()
