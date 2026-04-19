"""
xTalent Graph - Real Publish Demo

This demo attempts to publish to real IPFS using Kubo.
If Kubo is not running, it falls back gracefully with clear instructions.
"""

from xtalent.core import XTalentCV, Status, Availability, SkillCategory, SalaryExpectation
from xtalent.publish import TalentPublisher
from xtalent.backends.inmemory import InMemoryIPFS
import sys
from datetime import datetime

def build_demo_cv() -> XTalentCV:
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.utcnow(),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=68,
        full_name="Petrus Giesbers",
        title="AI Developer & Founder, Netvista Media SL",
        summary="Building xTalent Graph — the open, decentralized talent protocol for the agent era.",
        experience="**Founder & AI Developer** — Netvista Media SL\n"
                   "• Architecting xTalent Graph: open IPFS-based talent discovery protocol",
        projects="**xTalent Graph** — Open LLM-native talent protocol on IPFS",
        skills_matrix=[
            SkillCategory(category="AI", items=["AI Tool Development", "Protocol Design", "Claude Code"], level="intermediate"),
            SkillCategory(category="Infrastructure", items=["IPFS", "Decentralized Systems"], level="intermediate")
        ],
        salary_expectation=SalaryExpectation(min=85000, currency="EUR", remote_only=True, equity_preference="high"),
        location_prefs=["Remote"]
    )

def main():
    print("🚀 xTalent Graph - Real Publish Demo\n")

    cv = build_demo_cv()

    # Try real Kubo IPFS first
    try:
        from xtalent.backends.kubo import KuboIPFS
        print("🔗 Connecting to Kubo IPFS...")
        ipfs_backend = KuboIPFS()
        print("✅ Connected to real IPFS daemon\n")
        real_publish = True
    except Exception as e:
        print("⚠️  Kubo IPFS not available — falling back to InMemoryIPFS")
        print(f"   Error: {e}")
        print("   Start Kubo with: docker compose -f docker-compose.dev.yml up -d kubo\n")
        ipfs_backend = InMemoryIPFS()
        real_publish = False

    publisher = TalentPublisher(ipfs=ipfs_backend)

    print("Publishing CV for @tool_rate to Talent Graph...\n")
    result = publisher.publish(cv)

    print("✅ SUCCESS!\n")
    print(f"CID          : {result.ipfs_cid}")
    
    if real_publish:
        print(f"IPFS Gateway : https://ipfs.io/ipfs/{result.ipfs_cid}")
        print(f"Public URL   : https://talent.x.ai/@tool_rate/cv-v1.md")
        print("\n🎉 Your CV is now permanently stored on the public IPFS network!")
    else:
        print(f"Simulated URL: https://talent.x.ai/@tool_rate/cv-v1.md")
        print("\n⚠️  This was a simulation (InMemoryIPFS).")
        print("   The data only exists during this run.")

    print("\n" + "="*70)
    print("Next step: Run with real IPFS")
    print("   docker compose -f docker-compose.dev.yml up -d kubo")
    print("   Then run this demo again — it will automatically use real IPFS.")
    print("="*70)

if __name__ == "__main__":
    main()