"""
xTalent Graph - Publish Demo

A clean, honest demo that tries real Kubo IPFS first.
Falls back gracefully if Kubo is not running.
"""

from datetime import datetime, UTC
from xtalent.core import XTalentCV
from xtalent.publish import TalentPublisher, InMemoryIPFS

def build_demo_cv() -> XTalentCV:
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.now(UTC),
        status="open",
        availability="looking",
        freshness_score=68,
        full_name="Petrus Giesbers",
        title="AI Developer & Founder, Netvista Media SL",
        summary="Building xTalent Graph — the open, decentralized talent protocol for the agent era.",
        experience="**Founder & AI Developer** — Netvista Media SL\n"
                   "• Architecting xTalent Graph: open IPFS-based talent discovery protocol",
        projects="**xTalent Graph** — Open LLM-native talent protocol on IPFS",
        skills_matrix=[
            {"category": "AI", "items": ["AI Tool Development", "Protocol Design"], "level": "intermediate"},
            {"category": "Infrastructure", "items": ["IPFS", "Decentralized Systems"], "level": "intermediate"}
        ],
        salary_expectation={"min": 85000, "currency": "EUR", "remote_only": True, "equity_preference": "high"},
        location_prefs=["Remote"]
    )

if __name__ == "__main__":
    print("🚀 xTalent Graph - Publish Demo\n")

    cv = build_demo_cv()

    # Try real Kubo IPFS
    try:
        from xtalent.backends.kubo import KuboIPFS
        print("🔗 Connecting to real Kubo IPFS...")
        ipfs = KuboIPFS()
        ipfs.version()  # live probe — trigger fallback here, not mid-publish
        print("✅ Connected to real decentralized IPFS!\n")
        real_mode = True
    except Exception:
        print("⚠️  Kubo IPFS not running → using InMemoryIPFS (demo mode)")
        print("   → To use real IPFS: docker compose -f docker-compose.dev.yml up -d kubo\n")
        ipfs = InMemoryIPFS()
        real_mode = False

    publisher = TalentPublisher(ipfs=ipfs)

    print("Publishing your CV to the Talent Graph...\n")
    result = publisher.publish(cv)

    print("✅ SUCCESS!\n")
    print(f"Handle  : {cv.handle}")
    print(f"Version : v{cv.version}")
    print(f"CID     : {result.cid}")

    if real_mode:
        print(f"Gateway : https://ipfs.io/ipfs/{result.cid}")
        print("\n🎉 Your CV is now permanently stored on the public IPFS network!")
    else:
        print("Simulated URL : https://talent.x.ai/@tool_rate/cv-v1.md")
        print("\n⚠️  This is a simulation — the CV only exists in memory.")

    print("\n" + "═" * 65)
    if real_mode:
        print("Pinned locally — open it in your browser:")
        print(f"   http://localhost:8080/ipfs/{result.cid}")
        print("Or share the public gateway link above.")
    else:
        print("Want real decentralized storage?")
        print("   docker compose -f docker-compose.dev.yml up -d kubo")
        print("   Then run this demo again.")
    print("═" * 65)
