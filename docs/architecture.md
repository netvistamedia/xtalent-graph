# Architecture

xTalent Graph separates three concerns:

1. **Immutable CV history** — every `cv-vN.md` is content-addressed and pinned (IPFS). It never changes.
2. **Mutable profile root** — a small JSON document with `latest_cid`, live status, availability, freshness. It is the *only* thing that changes.
3. **Semantic index** — profile roots are embedded and indexed for agent queries. The index is a derived view; it can be rebuilt from (1) and (2) at any time.

This layering is deliberate. Permanence lives in IPFS. Change lives in the profile root. Queryability lives in the index. Each layer can be swapped without disturbing the others.

## Data flow

```
Author              Protocol                                 Consumer
──────              ────────                                 ────────

 cv-v3.md ──► TalentPublisher ──► IPFS (pin) ──► CID
                    │
                    ▼
              ProfileRoot
              { handle: "@ada",
                latest_cid: "bafy…",
                status: open,
                availability: looking,
                freshness_score: 96,
                updated_at: … }
                    │
                    ▼
             TalentSearchIndex ◄──── Embedder (Grok / OpenAI / …)
                    │
                    ▼
              /search API ──────────────────────────────► agent
                                                              │
              /cv/{cid}   ◄─────────── resolve content ───────┘
```

## Immutability, by construction

A `cv-vN.md` is serialized from an `XTalentCV` to YAML frontmatter + Markdown body. Its CID is `hash(bytes)`. Two different authors serializing the same CV produce the same CID. Corrections are never in-place edits — they are new versions (`cv-v4.md`) producing a new CID, and the profile root's `latest_cid` is updated to point at it.

This gives us:

- **Permanent history.** Old versions are still retrievable by CID.
- **Tamper evidence.** Any claim about "what my CV said on date X" reduces to "did CID Y exist on date X."
- **Offline verification.** An agent that has already resolved a CID never needs to trust the server again.

## Mutable state, kept tiny

The profile root is intentionally minimal:

```json
{
  "schema": "xtalent/profile-root/v1",
  "handle": "@ada",
  "latest_cid": "bafy...",
  "version": 3,
  "status": "open",
  "availability": "looking",
  "next_available_date": null,
  "freshness_score": 96,
  "updated_at": "2026-04-18T11:02:00Z",
  "tombstoned": false
}
```

Anything beyond these live signals belongs in the immutable CV. Keeping the root small means:

- Updates are cheap (no re-pinning of the large document).
- Signing and verification stay simple.
- Cache invalidation is trivial.

## Pluggable backends

Three interfaces keep the core decoupled:

| Interface       | Purpose                                 | Reference impl      | Production candidates           |
|-----------------|-----------------------------------------|---------------------|---------------------------------|
| `IPFSClient`    | Pin and fetch CV bytes                  | `InMemoryIPFS`      | Kubo HTTP, web3.storage, Pinata |
| `Embedder`      | Text → vector                           | `DeterministicEmbedder`, `GrokEmbedder` (stub) | xAI, OpenAI, Voyage, local ST  |
| `VectorIndex`   | Upsert / search vectors with metadata   | `InMemoryIndex`     | Qdrant, pgvector, Pinecone      |

Each has a narrow interface. Implementations can be swapped without touching `core.py`.

## Privacy and anti-spam

- Contact handles are opt-in, under a `privacy` block on the CV.
- GDPR-style removal is a **tombstone** on the profile root (`tombstoned: true`, optional `tombstone_reason`). The immutable CVs remain content-addressed, but the protocol-level discoverability signal is off.
- Rate-limiting and abuse policy live at the API boundary, not in the protocol. Reference server exposes hooks; production deployments plug in their own.

## What is not in scope (yet)

- Identity / key management (planned: ed25519-signed profile roots).
- Federation across trust roots (planned).
- Rich graph edges beyond `latest_cid → cv` (planned: works-with, mentored-by).

The protocol is deliberately small so it can actually be adopted.
