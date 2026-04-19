# Schema

Two documents form the protocol:

1. **`xtalent/cv/v1`** — immutable, serialized as Markdown with YAML frontmatter.
2. **`xtalent/profile-root/v1`** — mutable, serialized as JSON.

Both are versioned independently. Breaking changes bump the version suffix (`v1` → `v2`); backward-compatible additions do not.

---

## `xtalent/cv/v1`

### File convention

One file per version: `cv-v{N}.md`, where `N` is a positive integer, monotonically increasing per handle.

### Frontmatter (YAML)

| Field                  | Type                | Required | Notes                                                                 |
|------------------------|---------------------|----------|-----------------------------------------------------------------------|
| `schema`               | string              | yes      | Must equal `xtalent/cv/v1`.                                           |
| `handle`               | string              | yes      | Matches `^@[\w]+$` (e.g. `@ada`). Unique per trust root.              |
| `version`              | integer ≥ 1         | yes      | Increments monotonically per handle.                                  |
| `last_updated`         | RFC3339 timestamp   | yes      | When this CV version was authored.                                    |
| `status`               | enum                | yes      | `open`, `passive`, `closed`, `hired`, `inactive`.                     |
| `availability`         | enum                | yes      | `looking`, `not_looking`, `next_available`.                           |
| `next_available_date`  | RFC3339 \| null     | no       | Required iff `availability == next_available`.                        |
| `expires_at`           | RFC3339 \| null     | no       | Optional hard expiry for this version's signal.                       |
| `freshness_score`      | integer 0..100      | yes      | Authored freshness signal. Indexers may recompute.                    |
| `salary_expectation`   | object \| null      | no       | Free-form, e.g. `{currency: EUR, min: 120000, max: 160000}`.          |
| `location_prefs`       | list of string      | no       | e.g. `["remote", "Amsterdam", "Berlin"]`.                             |
| `skills_matrix`        | list of object      | no       | e.g. `[{name: rust, years: 6, level: expert}]`.                       |
| `ai_twin_enabled`      | boolean             | yes      | If `true`, the holder permits agent-to-agent Q&A against this CV.     |
| `privacy`              | object              | yes      | `{contact: {handle: @ada, email?: …}, discoverable: true, …}`.        |

### Body (Markdown)

The body is plain Markdown. Four canonical sections exist — three **required**, one **optional**:

- `## Summary` — required
- `## Experience` — required
- `## Projects` — required
- `## Endorsements` — optional

The body may contain additional sections. Tooling must not reject unknown sections.

### Example

See [`schema/example-cv-v1.md`](../schema/example-cv-v1.md).

### Immutability

Once a `cv-vN.md` is pinned and its CID is referenced by a profile root, the bytes must not change. Corrections are issued as `cv-v{N+1}.md`.

---

## `xtalent/profile-root/v1`

### Shape

```json
{
  "schema": "xtalent/profile-root/v1",
  "handle": "@ada",
  "latest_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
  "version": 3,
  "status": "open",
  "availability": "looking",
  "next_available_date": null,
  "freshness_score": 96,
  "updated_at": "2026-04-18T11:02:00Z",
  "tombstoned": false,
  "tombstone_reason": null,
  "pubkey": "ed25519:MCowBQYDK2VwAyEA…",
  "signature": "ed25519:iRV5g…"
}
```

### Fields

| Field                  | Type              | Required | Notes                                                     |
|------------------------|-------------------|----------|-----------------------------------------------------------|
| `schema`               | string            | yes      | Must equal `xtalent/profile-root/v1`.                     |
| `handle`               | string            | yes      | Matches `^@[\w]+$`. Primary key for the root.             |
| `latest_cid`           | string            | yes      | Content ID of the current `cv-vN.md`.                     |
| `version`              | integer ≥ 1       | yes      | Mirrors the CV version this root points at.               |
| `status`               | enum              | yes      | Mirrors the CV's `status` at the time of last update.     |
| `availability`         | enum              | yes      | Mirrors the CV's `availability`.                          |
| `next_available_date`  | RFC3339 \| null   | no       | As in the CV.                                             |
| `freshness_score`      | integer 0..100    | yes      | May be recomputed by the indexer.                         |
| `updated_at`           | RFC3339           | yes      | When the root was last written.                           |
| `tombstoned`           | boolean           | yes      | If `true`, the handle is withdrawn from discovery.        |
| `tombstone_reason`     | string \| null    | no       | Optional human-readable reason.                           |
| `pubkey`               | string \| null    | no       | Ed25519 public key, format `ed25519:<base64>`. See Signing. |
| `signature`            | string \| null    | no       | Ed25519 signature, format `ed25519:<base64>`. See Signing. |

### Tombstones

`DELETE /profile/{handle}` sets `tombstoned: true`. Indexers must drop the profile root from search results. Immutable CVs remain resolvable by CID — this is by design: the protocol removes *discoverability*, not history.

### Signing

Both `pubkey` and `signature` are optional fields added under
`xtalent/profile-root/v1` — they are additive and do **not** require a
schema version bump. Implementations that predate signing must ignore
unknown fields within the current major version.

When present, a signature is an Ed25519 signature over the canonical JSON
form of the root **with `pubkey` included** and **`signature` excluded**:

1. Serialize the root (by alias, mode=json).
2. Remove the `signature` key (if present).
3. `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
4. UTF-8 encode.
5. Ed25519-sign.

Reference implementation: [`xtalent.signing`](../python/src/xtalent/signing.py).

A valid signature attests to **self-consistency** only: "this pubkey
signed this root." Binding `pubkey` → `handle` (i.e. answering "is this
key really Ada's?") is an *out-of-band* trust problem — DNS TXT records,
central registries, Keybase-style proof chains — and is not in scope for
v0.1.

`tombstone()` on an existing root clears `signature`: changing
`tombstoned` / `updated_at` invalidates the previous signature, and the
caller must re-sign.

---

## Compatibility

- New optional frontmatter fields may be added within a version.
- Removing or repurposing a field requires a version bump.
- Indexers must ignore unknown fields within the current major version.
