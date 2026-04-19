"""
xTalent Graph - Publish Demo (Real IPFS Ready)

This demo tries to use real Kubo IPFS first.
If Kubo is not running, it falls back to InMemoryIPFS with clear instructions.
"""

from datetime import datetime
from xtalent.core import XTalentCV
from xtalent.publish import TalentPublisher
from xtalent.publish import InMemoryIPFS

def build_demo_cv() -> XTalentCV:
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.utcnow(),
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
        print("🔗 Trying real Kubo IPFS...")
        ipfs = KuboIPFS()
        ipfs.version()  # health check — forces a live request so fallback triggers now, not mid-publish
        mode = "REAL IPFS (Kubo)"
        print("✅ Connected to real Kubo IPFS\n")
    except Exception as e:
        print("⚠️  Kubo IPFS not available — using InMemoryIPFS (demo mode)")
        print(f"   Error: {type(e).__name__}: {e}")
        print("   → Start Kubo: docker compose -f docker-compose.dev.yml up -d kubo\n")
        ipfs = InMemoryIPFS()
        mode = "InMemoryIPFS (demo only)"

    publisher = TalentPublisher(ipfs=ipfs)

    print(f"Publishing CV for @tool_rate using {mode}...\n")
    result = publisher.publish(cv)

    print("✅ SUCCESS!\n")
    print(f"Handle       : {cv.handle}")
    print(f"Version      : v{cv.version}")
    print(f"CID          : {result.cid if hasattr(result, 'cid') else result.get('cid', 'N/A')}")

    if "Kubo" in mode:
        print(f"IPFS Gateway : https://ipfs.io/ipfs/{result.cid if hasattr(result, 'cid') else result.get('cid')}")
        print("\n🎉 Your CV is now permanently stored on the decentralized IPFS network!")
    else:
        print("Simulated URL: https://talent.x.ai/@tool_rate/cv-v1.md")
        print("\n⚠️  This was a simulation. Data only exists during this run.")

    print("\n" + "═" * 70)
    print("To use real IPFS:")
    print("   docker compose -f docker-compose.dev.yml up -d kubo")
    print("   Then run this demo again.")
    print("═" * 70)