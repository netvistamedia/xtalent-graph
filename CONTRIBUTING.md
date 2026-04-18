# Contributing to xTalent Graph

Thanks for your interest. This is an early-stage open protocol and we welcome contributions to the schema, reference implementations, adapters, docs, and tests.

## Principles

1. **Protocol first, implementation second.** Schema changes require an RFC-style PR touching `docs/schema.md` and a version bump (`xtalent/cv/vN` → `xtalent/cv/vN+1`). Never silently break existing CVs.
2. **Immutability of published CVs.** `cv-vN.md` files, once pinned, are immutable by construction (content-addressed). Corrections happen via new versions, never edits.
3. **Mutable state is minimal.** The profile root carries only what *must* change (pointer to latest CV, availability, freshness, tombstone). Keep it small.
4. **Pluggable backends.** Every external system (IPFS client, embedder, vector store) must sit behind a narrow interface. No hard dependency on a specific vendor.
5. **Agent-first ergonomics.** APIs should be legible to a language model with no prior context. Stable fields, stable URIs, stable error shapes.

## How to contribute

### Bug reports
Open an issue with a minimal reproduction. If the bug is a schema ambiguity, cite the exact line in `docs/schema.md`.

### Schema changes
1. Open an issue labelled `schema`.
2. Describe the motivation and include a before/after example.
3. Reach rough consensus before opening a PR.
4. PR updates `docs/schema.md`, bumps the schema version, adds a migration note, and updates `schema/example-cv-vN.md`.

### Code changes

#### Python (`python/`)
```bash
cd python
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```
- Python 3.12+.
- Pydantic v2 for all data models.
- Public functions require type hints and docstrings.
- Tests for new behavior. No snapshot-only tests for core logic.

#### TypeScript (`typescript/`)
```bash
cd typescript
npm install
npm run build
npm test
```
- TypeScript in `strict` mode.
- ESM only. Node 20+.
- No `any`. Narrow types at module boundaries.

### Commit and PR style
- Present-tense, imperative subject line (`add Kubo IPFS adapter`, not `added`).
- One logical change per PR.
- Link the issue in the PR body.
- CI must be green.

## Good first issues
- Implement `KuboIPFS` against the local Kubo HTTP API.
- Implement `ChromaIndex` or `PgVectorIndex` behind the `VectorIndex` protocol.
- Translate common `SearchFilters` shapes into native Qdrant `Filter` objects so the adapter can push filters server-side.
- Add an ed25519 signing helper for profile roots.
- Add a `cv-v2.md` schema draft for multilingual CVs.

## Releasing
Maintainers only. Tagged releases follow semver on the reference implementations, independent of the protocol schema version.

## Code of Conduct
Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
