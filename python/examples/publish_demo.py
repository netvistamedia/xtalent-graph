"""
xTalent Graph - Publish Demo

Real decentralized storage. Verifiable in real time.

Publishes a CV through the reference pipeline, then proves it actually
landed on the public network by fetching it back from Protocol Labs'
public gateway and checking the bytes are byte-identical to what we
pinned. Shows timing per phase and peer reachability.

Flags:
    --open    Open the public gateway URL in your browser at the end
              (real mode only).

Run:
    python -m examples.publish_demo
    python -m examples.publish_demo --open
"""

from __future__ import annotations

import os
import sys
import time
import webbrowser
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

import httpx

from xtalent.core import XTalentCV
from xtalent.publish import InMemoryIPFS, TalentPublisher

PUBLIC_GATEWAY = "https://ipfs.io/ipfs/{cid}"
LOCAL_GATEWAY = "http://localhost:8080/ipfs/{cid}"
VERIFY_TIMEOUT_S = 60.0
VERIFY_BACKOFF_S = (2.0, 4.0, 8.0, 15.0, 30.0)


# ---------------------------------------------------------------------------
# Sample CV
# ---------------------------------------------------------------------------


def build_demo_cv() -> XTalentCV:
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.now(UTC),
        status="open",
        availability="looking",
        freshness_score=72,
        full_name="Petrus Giesbers",
        title="AI Developer & Founder, Netvista Media SL",
        summary=(
            "Building xTalent Graph — the open, decentralized talent "
            "protocol for the agent era."
        ),
        experience=(
            "**Founder & AI Developer** — Netvista Media SL\n"
            "- Creating xTalent Graph: an open IPFS-based talent discovery protocol"
        ),
        projects="**xTalent Graph** — Open LLM-native talent protocol",
        skills_matrix=[
            {"name": "python", "years": 10, "level": "expert"},
            {"name": "protocol-design", "years": 1, "level": "intermediate"},
            {"name": "ipfs", "years": 1, "level": "intermediate"},
            {"name": "llm-orchestration", "years": 2, "level": "advanced"},
            {"name": "decentralized-storage", "years": 1, "level": "intermediate"},
        ],
        salary_expectation={
            "min": 85000,
            "currency": "EUR",
            "remote_only": True,
            "equity_preference": "high",
        },
        location_prefs=["Remote"],
    )


# ---------------------------------------------------------------------------
# Phase timing — prints "[n/N] label ........ 12ms ✓" style lines
# ---------------------------------------------------------------------------


class Phases:
    """Print aligned ``[n/N] label ........ 12ms ✓ (suffix)`` phase lines."""

    def __init__(self, total: int, dot_col: int = 44) -> None:
        self.total = total
        self.dot_col = dot_col
        self._n = 0
        self.durations_ms: dict[str, float] = {}

    def _prefix(self, label: str) -> str:
        self._n += 1
        return f"  [{self._n}/{self.total}] {label} "

    def _dots(self, prefix: str) -> str:
        return "." * max(2, self.dot_col - len(prefix))

    @contextmanager
    def step(self, label: str) -> Iterator[dict[str, str]]:
        prefix = self._prefix(label)
        print(prefix, end="", flush=True)
        extra: dict[str, str] = {}
        t0 = time.perf_counter()
        try:
            yield extra
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.durations_ms[label] = elapsed_ms
            print(f"{self._dots(prefix)} FAILED ({type(exc).__name__})")
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.durations_ms[label] = elapsed_ms
        suffix = extra.get("suffix", "")
        timing = f"{elapsed_ms:>5.0f}ms"
        tail = f"{self._dots(prefix)} {timing} ✓"
        if suffix:
            tail += f" {suffix}"
        print(tail)

    def skip(self, label: str, reason: str) -> None:
        prefix = self._prefix(label)
        print(f"{prefix}{self._dots(prefix)}     —  (skipped: {reason})")


# ---------------------------------------------------------------------------
# Backend selection — real Kubo with graceful fallback
# ---------------------------------------------------------------------------


def select_backend(kubo_url: str = "http://localhost:5001"):
    """Return ``(client, backend_name, info)``. Never raises."""
    try:
        from xtalent.backends.kubo import KuboConnectionError, KuboIPFS
    except ImportError:
        return (
            InMemoryIPFS(),
            "memory",
            "xtalent[kubo] extra not installed",
        )
    ipfs = KuboIPFS(url=kubo_url)
    try:
        ipfs.version()
    except KuboConnectionError:
        ipfs.close()
        return InMemoryIPFS(), "memory", f"Kubo unreachable at {kubo_url}"
    return ipfs, "kubo", kubo_url


# ---------------------------------------------------------------------------
# Network reachability — peer count via Kubo swarm API
# ---------------------------------------------------------------------------


def count_swarm_peers(ipfs) -> int:
    """Return the number of peers Kubo is currently connected to. Best-effort."""
    try:
        resp = ipfs._client.post("/api/v0/swarm/peers")
    except Exception:
        return 0
    if resp.status_code != 200:
        return 0
    try:
        payload = resp.json()
    except ValueError:
        return 0
    peers = payload.get("Peers") or []
    return len(peers) if isinstance(peers, list) else 0


# ---------------------------------------------------------------------------
# Public-gateway verification — proves the content actually propagated
# ---------------------------------------------------------------------------


def verify_on_public_gateway(cid: str, expected: bytes) -> tuple[float, int]:
    """Fetch ``cid`` from ipfs.io and check byte-equality with ``expected``.

    Retries with exponential backoff up to ``VERIFY_TIMEOUT_S``.
    Returns ``(elapsed_ms, attempts)``.
    Raises :class:`TimeoutError` if propagation did not complete in time,
    or :class:`ValueError` if retrieved bytes differ from what was pinned.
    """
    url = PUBLIC_GATEWAY.format(cid=cid)
    start = time.perf_counter()
    attempts = 0
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for delay in (0.0, *VERIFY_BACKOFF_S):
            if delay:
                time.sleep(delay)
            if time.perf_counter() - start > VERIFY_TIMEOUT_S:
                break
            attempts += 1
            try:
                resp = client.get(url)
            except httpx.HTTPError:
                continue
            if resp.status_code != 200 or not resp.content:
                continue
            if resp.content != expected:
                raise ValueError(
                    f"public gateway returned {len(resp.content)} bytes; "
                    f"expected {len(expected)} (byte mismatch)"
                )
            return (time.perf_counter() - start) * 1000, attempts
    raise TimeoutError(
        f"public gateway did not serve {cid} within {VERIFY_TIMEOUT_S:.0f}s"
    )


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def _banner() -> str:
    return (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║              xTalent Graph — Publish Demo                    ║\n"
        "║     Real decentralized storage. Verifiable in real time.     ║\n"
        "╚══════════════════════════════════════════════════════════════╝"
    )


def _short(cid: str) -> str:
    return cid if len(cid) <= 18 else f"{cid[:10]}…{cid[-6:]}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    open_browser = "--open" in sys.argv[1:]

    print(_banner())
    print()

    phases = Phases(total=5)

    with phases.step("Building CV for @tool_rate"):
        cv = build_demo_cv()

    with phases.step("Connecting to IPFS backend") as info:
        ipfs, backend, detail = select_backend(
            os.environ.get("XTALENT_KUBO_URL", "http://localhost:5001")
        )
        info["suffix"] = "(Kubo)" if backend == "kubo" else "(fallback: InMemory)"

    with phases.step("Pinning CV"):
        publisher = TalentPublisher(ipfs=ipfs)
        record = publisher.publish(cv)
        cv_bytes = record.cv_markdown.encode("utf-8")

    if backend == "kubo":
        with phases.step("Announcing to IPFS network") as info:
            peers = count_swarm_peers(ipfs)
            info["suffix"] = f"({peers} peers connected)"

        verify_elapsed_ms: float | None = None
        verify_attempts: int | None = None
        verify_error: str | None = None
        with phases.step("Verifying on public gateway") as info:
            try:
                verify_elapsed_ms, verify_attempts = verify_on_public_gateway(
                    record.cid, cv_bytes
                )
                info["suffix"] = (
                    f"(byte-identical, {verify_attempts} "
                    f"attempt{'s' if verify_attempts != 1 else ''})"
                )
            except (TimeoutError, ValueError) as exc:
                verify_error = str(exc)
                raise
    else:
        phases.skip("Announcing to IPFS network", "demo backend")
        phases.skip("Verifying on public gateway", "demo backend")
        verify_elapsed_ms = None
        verify_error = detail

    # ---- summary ----
    bar = "═" * 64
    print()
    print(bar)
    print(f"  Handle    {cv.handle}")
    print(f"  Version   v{cv.version}")
    print(f"  CID       {record.cid}")
    print(bar)
    public_url = PUBLIC_GATEWAY.format(cid=record.cid)
    local_url = LOCAL_GATEWAY.format(cid=record.cid)
    if backend == "kubo":
        print(f"  Public    {public_url}")
        print(f"  Local     {local_url}")
    else:
        print(f"  URL       {public_url}   (won't resolve — fallback backend)")
    print()

    if backend == "kubo" and verify_elapsed_ms is not None:
        total_ms = sum(phases.durations_ms.values())
        print(
            f"  ✓ Your CV is publicly verifiable on the decentralized web."
        )
        print(
            f"    {total_ms:.0f}ms from build to globally reachable "
            f"({verify_elapsed_ms:.0f}ms on the public gateway)."
        )
    else:
        print("  ⚠️  Fallback mode — bytes live only in this process.")
        print(f"     Reason: {verify_error}")
        print("     Start Kubo to publish for real:")
        print("       brew install ipfs && ipfs init && ipfs daemon")

    print()
    if backend == "kubo":
        if open_browser:
            print(f"  Opening {public_url} in your browser…")
            webbrowser.open(public_url)
        else:
            print(f"  Open in browser:  python -m examples.publish_demo --open")

    close = getattr(ipfs, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    main()
