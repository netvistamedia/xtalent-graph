# xTalent Graph

> The open, LLM-native talent protocol for the agent era.

**Status:** Early open protocol — contributions welcome.

[![CI](https://github.com/OWNER/xtalent-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/xtalent-graph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/typescript-strict-blue.svg)](https://www.typescriptlang.org/)

---

## Why this exists

LinkedIn is a walled garden. CVs are PDFs. Recruiters spam. AI agents can't reliably read, reason over, or act on human career data without scraping captchas and fighting rate limits.

**xTalent Graph** is the anti-LinkedIn: an open, content-addressed, LLM-native protocol where every CV is a structured Markdown document pinned on IPFS, indexed as embeddings, and searchable by any agent on Earth through a public API.

## What it is

- **Immutable CV history** — every version of your CV is a `cv-vN.md` file (YAML frontmatter + Markdown body), content-addressed on IPFS. History is permanent and verifiable.
- **Mutable profile root** — a small JSON document points at your latest CV and carries live signals (availability, location, freshness timestamp). This is the only part that changes.
- **Semantic index** — profile roots are embedded and indexed. Agents can ask natural-language questions ("Rust engineer, remote EU, shipped a production rollup in the last year") and get ranked candidates.
- **Agent-first by design** — a stable JSON-over-HTTP API, stable schemas, stable URIs. No scraping. No login walls. No dark patterns.
- **Privacy and anti-spam primitives** — opt-in contact handles, revocable pointers, GDPR-shaped deletion via profile-root tombstones.

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

## Quick start — Python

```bash
cd python
pip install -e ".[dev]"
pytest
```

```python
from xtalent import XTalentCV, TalentPublisher, TalentSearchIndex
from xtalent.publish import InMemoryIPFS

cv = XTalentCV.from_markdown_file("../schema/example-cv-v1.md")
publisher = TalentPublisher(ipfs=InMemoryIPFS())
record = publisher.publish(cv)

index = TalentSearchIndex()
index.upsert(record)

for hit in index.search("staff engineer, rust, distributed systems", k=5):
    print(hit.score, hit.record.profile_root.handle)
```

Run the FastAPI server:

```bash
uvicorn xtalent.api:app --reload
```

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
const results = await client.search({
  query: "staff engineer, rust, distributed systems",
  k: 5,
});
for (const hit of results.hits) {
  console.log(hit.score, hit.record.profile_root.handle);
}
```

## Schema

See [`docs/schema.md`](docs/schema.md) and [`schema/example-cv-v1.md`](schema/example-cv-v1.md).

Every CV is a single Markdown file:

```markdown
---
schema: xtalent/cv/v1
handle: ada
version: 3
published_at: 2026-04-12T09:00:00Z
headline: Staff software engineer, distributed systems
skills: [rust, distributed-systems, consensus, observability]
location: { city: Amsterdam, country: NL, remote: true }
availability: open
---

## Summary
...

## Experience
...
```

## API

See [`docs/api.md`](docs/api.md) for the full OpenAPI shape. In short:

| Method | Path               | Purpose                                |
|--------|--------------------|----------------------------------------|
| POST   | `/publish`         | Pin a new CV version and update root   |
| GET    | `/profile/{handle}`| Fetch the mutable profile root         |
| GET    | `/cv/{cid}`        | Fetch an immutable CV by content ID    |
| POST   | `/search`          | Semantic search over profile roots     |
| DELETE | `/profile/{handle}`| Tombstone the profile root (GDPR)      |

## Architecture

See [`docs/architecture.md`](docs/architecture.md).

## Roadmap

- [x] Core schema (`xtalent/cv/v1`)
- [x] Reference publisher with pluggable IPFS client
- [x] In-memory vector index with pluggable `Embedder`
- [x] FastAPI reference server
- [x] TypeScript SDK
- [ ] Real IPFS adapters (Kubo HTTP, web3.storage, Pinata)
- [ ] Qdrant / pgvector backends
- [ ] Signed profile roots (ed25519)
- [ ] Graph-native relationships (works-with, mentored-by)
- [ ] Federated indexing across multiple trust roots

## Contributing

We accept PRs for schemas, adapters, docs, and tests. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Good first issues:
- Implement a `KuboIPFS` adapter against the local IPFS HTTP API.
- Implement a `QdrantIndex` backend behind the `TalentSearchIndex` interface.
- Add signing for profile roots.

## License

[MIT](LICENSE) — use it, fork it, build on it.
