<p align="center">
  <img src="docs/assets/banner.jpg" alt="xTalent Graph — replacing LinkedIn for the agent era" width="100%" />
</p>

# xTalent Graph

> The open, LLM-native talent protocol for the agent era.

**Status:** Early open protocol — contributions welcome.

[![CI](https://github.com/netvistamedia/xtalent-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/netvistamedia/xtalent-graph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript strict](https://img.shields.io/badge/typescript-strict-3178c6.svg)](https://www.typescriptlang.org/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Why this exists

LinkedIn is a walled garden. CVs are PDFs. Recruiters spam. AI agents can't reliably read, reason over, or act on human career data without scraping captchas and fighting rate limits.

**xTalent Graph** is the anti-LinkedIn: an open, content-addressed, LLM-native protocol where every CV is a structured Markdown document pinned on IPFS, indexed as embeddings, and searchable by any agent on Earth through a public API.

### How it compares

|                             | xTalent Graph | LinkedIn | Resume PDFs |
|-----------------------------|---------------|----------|-------------|
| **Agent access**            | First-class public API | Blocked / scraping | None (opaque binary) |
| **Data ownership**          | The author owns the bytes, pinned on IPFS | LinkedIn owns and gates the data | The author owns a file |
| **Immutable history**       | Every version has a CID, permanent | Revisions overwrite silently | Multiple versions drift |
| **Semantic search**         | Native, model-pluggable | Keyword + paid filters | None |
| **Privacy controls**        | Tombstone + opt-in discovery | Profile fields, closed-source rules | You email the PDF |
| **Spam model**              | No mass outreach primitive | Ad-driven inbox | Cold email |
| **Cost to the author**      | $0 (protocol) | Free tier + paid upsell | $0 |
| **Verifiable provenance**   | CID + planned ed25519 signing | Platform trust only | None |

## What it is

- **Immutable CV history** — every version of your CV is a `cv-vN.md` file (YAML frontmatter + Markdown body), content-addressed on IPFS. History is permanent and verifiable.
- **Mutable profile root** — a small JSON document points at your latest CV and carries live signals (availability, location, freshness). This is the only part that changes.
- **Semantic index** — profile roots are embedded and indexed. Agents can ask natural-language questions ("Rust engineer, remote EU, shipped a production consensus implementation in the last year") and get ranked candidates.
- **Agent-first by design** — a stable JSON-over-HTTP API, stable schemas, stable URIs. No scraping. No login walls. No dark patterns.
- **Privacy and anti-spam primitives** — opt-in contact handles, revocable pointers, GDPR-shaped deletion via profile-root tombstones.

## Quick start — Python

```bash
git clone https://github.com/netvistamedia/xtalent-graph
cd xtalent-graph/python
pip install -e ".[dev]"
pytest
python ../examples/demo.py
```

```python
from xtalent import TalentPublisher, TalentSearchIndex, XTalentCV
from xtalent.publish import InMemoryIPFS

cv = XTalentCV.from_markdown_file("../schema/example-cv-v1.md")
publisher = TalentPublisher(ipfs=InMemoryIPFS())
record = publisher.publish(cv)

index = TalentSearchIndex()
index.upsert(record)

for hit in index.search("staff engineer, rust, distributed systems", k=5):
    print(hit.score, hit.record.profile_root.handle)
```

Run the FastAPI reference server:

```bash
uvicorn xtalent.api:app --reload
open http://localhost:8000/docs
```

### Use Qdrant as the vector backend

The in-memory index is great for tests. For anything real, use the Qdrant
adapter that ships in the box:

```bash
pip install "xtalent[qdrant]"
docker compose -f docker-compose.dev.yml up -d   # local Qdrant on :6333
XTALENT_QDRANT_URL=http://localhost:6333 uvicorn xtalent.api:app --reload
```

The reference server auto-detects the env var and routes all `/publish`,
`/search`, and `/profile` traffic through the Qdrant-backed index. See
[`docs/architecture.md`](docs/architecture.md#qdrant-backend) for details.

## Quick start — TypeScript

```bash
cd typescript
npm install
npm run build
npx tsx example.ts
```

```ts
import { XTalentClient } from "xtalent-graph";

const client = new XTalentClient({ baseUrl: "http://localhost:8000" });
await client.publish(cvMarkdown);

const results = await client.search({
  query: "staff engineer, rust, distributed systems",
  k: 5,
});
for (const hit of results.hits) {
  console.log(hit.score, hit.record.profile_root.handle);
}
```

## Try a sample CV

A ready-to-publish Markdown CV is included at
[`schema/example-cv-v1.md`](schema/example-cv-v1.md) — YAML frontmatter plus
human-readable Markdown body. Use it as a template.

```markdown
---
schema: xtalent/cv/v1
handle: "@ada"
version: 1
last_updated: 2026-04-18T09:00:00Z
status: open
availability: looking
freshness_score: 96
skills_matrix:
  - { name: rust, years: 6, level: expert }
  - { name: distributed-systems, years: 5, level: expert }
location_prefs: [remote, Amsterdam]
ai_twin_enabled: true
privacy:
  contact: { handle: "@ada" }
  discoverable: true
---

# Ada Lovelace
_Staff software engineer, distributed systems_

## Summary
...
## Experience
...
## Projects
...
```

## How it works

```
┌───────────────┐     publish     ┌──────────────┐     index     ┌────────────────┐
│  cv-v3.md     │ ──────────────► │ IPFS (CID)   │ ─────────────►│ Vector + Graph │
│  (immutable)  │                 │ permanent    │               │ (mutable view) │
└───────────────┘                 └──────────────┘               └────────────────┘
        ▲                                 ▲                              ▲
        │                                 │                              │
        │            points to            │            ask               │
        │         ┌────────────────┐      │      ┌────────────────┐      │
        └─────────│ profile-root   │──────┘      │  any LLM agent │──────┘
                  │ (mutable JSON) │             │  /search API   │
                  └────────────────┘             └────────────────┘
```

1. You author `cv-v3.md` locally.
2. `TalentPublisher` validates it, pins it to IPFS, and updates your profile root.
3. `TalentSearchIndex` embeds the profile root and makes it searchable.
4. Any agent queries the public `/search` endpoint and resolves the pinned CV content via IPFS.

Full architecture: [`docs/architecture.md`](docs/architecture.md).

## API

See [`docs/api.md`](docs/api.md) for the full spec. In short:

| Method | Path               | Purpose                                |
|--------|--------------------|----------------------------------------|
| POST   | `/publish`         | Pin a new CV version and update root   |
| GET    | `/profile/{handle}`| Fetch the mutable profile root         |
| GET    | `/cv/{cid}`        | Fetch an immutable CV by content ID    |
| POST   | `/search`          | Semantic search over profile roots     |
| DELETE | `/profile/{handle}`| Tombstone the profile root (GDPR)      |

## Schema

Two documents form the protocol:

1. `xtalent/cv/v1` — immutable, serialized as Markdown with YAML frontmatter.
2. `xtalent/profile-root/v1` — mutable, serialized as JSON.

Authoritative reference: [`docs/schema.md`](docs/schema.md).

## Roadmap

- [x] Core schema (`xtalent/cv/v1`, `xtalent/profile-root/v1`)
- [x] Reference publisher with pluggable `IPFSClient`
- [x] In-memory vector index with pluggable `Embedder`
- [x] FastAPI reference server
- [x] TypeScript SDK
- [x] **Qdrant backend** — `xtalent.backends.qdrant.QdrantIndex`, installable via `pip install 'xtalent[qdrant]'`, auto-wired in the reference server via `XTALENT_QDRANT_URL`
- [x] `docker-compose.dev.yml` for local Qdrant
- [ ] **Ed25519-signed profile roots** — verifiable provenance is a prerequisite for agents to trust retrieved CVs
- [ ] Real IPFS adapters: Kubo HTTP, web3.storage, Pinata
- [ ] Chroma / pgvector backends (same interface, swap-in)
- [ ] Rate limiting, structured logging, and OpenTelemetry spans in the reference server
- [ ] **Graph-native relationships** — `works-with`, `mentored-by`, `co-founded`, `cited`. Turns the graph from a set of CVs into a navigable trust network; powers queries like "Rust engineers who worked with anyone from @kuiper-systems".
- [ ] Federated indexing across multiple trust roots
- [ ] Public reference deployment
- [ ] PyPI + npm releases

## Contributing

We accept PRs for schemas, adapters, docs, and tests. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Issue templates live under [`.github/ISSUE_TEMPLATE`](.github/ISSUE_TEMPLATE) for schema changes, adapter requests, and bugs.

Good first issues:
- Implement a `KuboIPFS` adapter against the local IPFS HTTP API.
- Implement `ChromaIndex` or `PgVectorIndex` behind the `VectorIndex` protocol.
- Add ed25519 signing helpers for profile roots.
- Translate common `SearchFilters` shapes to native Qdrant `Filter` objects (today the Qdrant adapter over-fetches and applies predicates client-side).

## Built with / inspired by

- **[IPFS](https://ipfs.tech)** — content addressing and immutability primitives.
- **[ActivityPub](https://www.w3.org/TR/activitypub/)** — federated, actor-centric public data.
- **[Solid](https://solidproject.org)** — user-owned structured data pods.
- **[Pydantic](https://docs.pydantic.dev)** & **[FastAPI](https://fastapi.tiangolo.com)** — the Python reference server.
- **[xAI Grok](https://x.ai)** — reference target for native LLM-side embeddings and orchestration.
- **[Qdrant](https://qdrant.tech)** / **[Chroma](https://www.trychroma.com)** — planned vector backends.
- **Plaintext Markdown.** The most durable format we have.

## Governance

The protocol is currently maintainer-led by [@netvistamedia](https://github.com/netvistamedia). Schema changes require an RFC-style PR (see [`CONTRIBUTING.md`](CONTRIBUTING.md)) and reach rough consensus in a GitHub issue before merge. Reference implementations are versioned independently on semver; the protocol bumps `xtalent/cv/vN` only on breaking changes.

## License

[MIT](LICENSE) — use it, fork it, build on it.
