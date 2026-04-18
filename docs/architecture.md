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

| Interface       | Purpose                                 | Reference impl                                 | Production candidates                          |
|-----------------|-----------------------------------------|------------------------------------------------|------------------------------------------------|
| `IPFSClient`    | Pin and fetch CV bytes                  | `InMemoryIPFS`, **`KuboIPFS`**                 | web3.storage, Pinata                           |
| `Embedder`      | Text → vector                           | `DeterministicEmbedder`, `GrokEmbedder` (stub) | xAI, OpenAI, Voyage, local sentence-transformers |
| `VectorIndex`   | Upsert / search vectors with metadata   | `InMemoryVectorIndex`, **`QdrantIndex`**       | Qdrant Cloud, pgvector, Pinecone, Chroma       |

Each has a narrow interface. Implementations can be swapped without touching `core.py`.

### Qdrant backend

Installed via the optional extra:

```bash
pip install "xtalent[qdrant]"
```

```python
from xtalent import TalentSearchIndex
from xtalent.backends.qdrant import QdrantIndex

# Embedded, in-process — great for tests and scripts.
index = TalentSearchIndex(index=QdrantIndex())

# Or a remote Qdrant server.
index = TalentSearchIndex(index=QdrantIndex(url="http://localhost:6333"))
```

The reference server auto-switches when `XTALENT_QDRANT_URL` is set in the
environment:

```bash
docker compose -f docker-compose.dev.yml up -d
XTALENT_QDRANT_URL=http://localhost:6333 uvicorn xtalent.api:app --reload
```

**Predicate semantics.** The generic `SearchPredicate` protocol (a plain
Python callable) cannot be translated to Qdrant's native `Filter` language
without knowing the caller's intent. The adapter therefore over-fetches
and applies predicates client-side. Results are correct; they are not
optimal when filters are highly selective. For large-scale deployments
with well-known filter shapes, call `QdrantIndex.client` directly and
issue native Qdrant queries.

## Kubo IPFS adapter

`xtalent.backends.kubo.KuboIPFS` is a production-grade
:class:`IPFSClient` against the Kubo HTTP API. It ships with the ``kubo``
extra (`pip install "xtalent[kubo]"`) and is auto-wired in the reference
server via the ``XTALENT_IPFS_MODE=kubo`` environment variable.

```python
from xtalent import TalentPublisher
from xtalent.backends.kubo import KuboIPFS

publisher = TalentPublisher(ipfs=KuboIPFS())   # http://localhost:5001
record = publisher.publish(cv)
# record.cid is now a real, pinned IPFS CID.
```

Key operations:

| Method                          | HTTP call                       | Purpose                                    |
|---------------------------------|---------------------------------|--------------------------------------------|
| `add_bytes(data, filename=None)`| `POST /api/v0/add`              | Add content; Kubo pins by default.         |
| `get_bytes(cid)`                | `POST /api/v0/cat?arg=<cid>`    | Fetch raw bytes.                           |
| `pin_cid(cid)`                  | `POST /api/v0/pin/add?arg=<cid>`| Explicitly pin a third-party CID.          |
| `version()`                     | `POST /api/v0/version`          | Health check; used by the server at boot.  |

`pin(data) -> cid` and `get(cid) -> bytes` on `KuboIPFS` mirror the
:class:`IPFSClient` protocol and delegate to `add_bytes` / `get_bytes`.
The protocol's `pin` is "persist and return CID"; IPFS's "pin this CID"
is a different operation, exposed here as `pin_cid` to avoid the name
collision.

Local dev: run `docker compose -f docker-compose.dev.yml up` and both
Qdrant and Kubo come up together.

## Signing and trust

Profile roots can carry an Ed25519 signature over their canonical JSON
form. Details in [`docs/schema.md`](schema.md#signing). Implementation:
[`xtalent.signing`](../python/src/xtalent/signing.py).

```python
from xtalent import generate_keypair, sign_profile_root, verify_profile_root

kp = generate_keypair()
signed_root = sign_profile_root(record.profile_root, kp.private_key)
verify_profile_root(signed_root)  # raises SignatureError on failure
```

The reference search index enforces signatures on demand:

```python
from xtalent import TalentSearchIndex

index = TalentSearchIndex(require_signatures=True)
# index.upsert(record) now raises SignatureError if the profile root
# is unsigned or its signature does not verify.
```

The reference server honors `XTALENT_REQUIRE_SIGNATURES=1`. A
fully-signed HTTP publish flow (client-supplied `updated_at` + signature
verified server-side before indexing) is an open v0.2 API design; until
then, use the Python library directly in deployments that enforce
signatures.

**What signatures do not prove.** A signature only shows that the
embedded pubkey signed the root. It does not prove the pubkey actually
belongs to the named handle — that is an out-of-band trust problem (DNS
TXT proofs, federated registries, Keybase-style chains). Designing that
trust layer is tracked as future work.

## Privacy and anti-spam

- Contact handles are opt-in, under a `privacy` block on the CV.
- GDPR-style removal is a **tombstone** on the profile root (`tombstoned: true`, optional `tombstone_reason`). The immutable CVs remain content-addressed, but the protocol-level discoverability signal is off.
- Rate-limiting and abuse policy live at the API boundary, not in the protocol. Reference server exposes hooks; production deployments plug in their own.

## What is not in scope (yet)

- Identity / key management (planned: ed25519-signed profile roots).
- Federation across trust roots (planned).
- Rich graph edges beyond `latest_cid → cv` (planned: works-with, mentored-by).

The protocol is deliberately small so it can actually be adopted.
