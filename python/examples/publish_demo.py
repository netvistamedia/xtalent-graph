"""
xTalent Graph - Publish Demo

Run with:
    python -m examples.publish_demo

This demo shows the full flow using InMemoryIPFS (fast & no setup).
When you're ready for real decentralized storage, swap to KuboIPFS (one line).
"""

from xtalent.core import XTalentCV, Status, Availability, SkillCategory, SalaryExpectation
from xtalent.publish import TalentPublisher
from xtalent.backends.inmemory import InMemoryIPFS
from datetime import datetime

def build_demo_cv() -> XTalentCV:
    """Realistic idea-stage CV for @tool_rate"""
    return XTalentCV(
        handle="@tool_rate",
        version=1,
        last_updated=datetime.utcnow(),
        status=Status.OPEN,
        availability=Availability.LOOKING,
        freshness_score=65,
        full_name="Petrus Giesbers",
        title="AI Developer & Founder, Netvista Media SL",
        summary="Building xTalent Graph — the open, LLM-native talent protocol for the agent era. "
                "Strong at rapid ideation and turning AI concepts into structured, searchable profiles.",
        experience="**Founder & AI Developer** — Netvista Media SL\n"
                   "• Developing xTalent Graph: open talent protocol using IPFS + semantic search",
        projects="**xTalent Graph** — Open protocol for AI-powered talent discovery\n"
                 "**ChatCasa** — AI speech bot for real estate recommendations\n"
                 "**SingSnap** — Vocal recording enhancement tool",
        skills_matrix=[
            SkillCategory(category="AI", items=["Claude Code", "Prompt Engineering", "AI Tool Ideation"], level="intermediate"),
            SkillCategory(category="Product", items=["Idea Generation", "Early-stage Development"], level="intermediate")
        ],
        salary_expectation=SalaryExpectation(min=80000, currency="EUR", remote_only=True, equity_preference="high"),
        location_prefs=["Remote"]
    )

if __name__ == "__main__":
    print("🚀 xTalent Graph - Publish Demo\n")

    cv = build_demo_cv()
    
    # Using InMemoryIPFS for zero-setup demo
    print("⚠️  Using InMemoryIPFS (demo mode)")
    print("   → Real IPFS (Kubo) support is available — see comment below\n")

    publisher = TalentPublisher(ipfs=InMemoryIPFS())

    print("Publishing CV for @tool_rate...\n")
    result = publisher.publish(cv)

    print("✅ Published successfully!\n")
    print(f"CID          : {result.ipfs_cid}")
    print(f"Simulated URL: https://talent.x.ai/@tool_rate/cv-v1.md")
    print(f"IPFS Gateway : https://ipfs.io/ipfs/{result.ipfs_cid}")
    print(f"Version      : v{cv.version}\n")

    print("Markdown preview:")
    markdown = cv.to_markdown()
    lines = markdown.splitlines()
    print("\n".join(lines[:18]))
    print("\n...\n")
    print("\n".join(lines[-12:]))

    print("\n" + "="*60)
    print("To use real decentralized IPFS (Kubo):")
    print("   1. Start Kubo:  docker compose -f docker-compose.dev.yml up -d kubo")
    print("   2. Change one line in this file:")
    print("      from xtalent.backends.inmemory import InMemoryIPFS")
    print("      from xtalent.backends.kubo import KuboIPFS")
    print("      publisher = TalentPublisher(ipfs=KuboIPFS())")
    print("="*60)