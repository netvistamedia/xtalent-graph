# HTTP API

Reference implementation: `xtalent.api:app` (FastAPI). Every route returns JSON. All timestamps are RFC3339 in UTC.

## Base errors

```json
{
  "error": {
    "code": "not_found" | "invalid_request" | "conflict" | "tombstoned",
    "message": "human-readable",
    "details": { "...": "..." }
  }
}
```

HTTP status codes follow REST conventions (`400`, `404`, `409`, `410`, `500`).

---

## `POST /publish`

Pin a new CV version and update the profile root.

**Request**

```json
{
  "cv_markdown": "---\nschema: xtalent/cv/v1\n...\n---\n\n## Summary\n..."
}
```

**Response `200`**

```json
{
  "handle": "@ada",
  "cid": "bafy...",
  "profile_root": { "...": "see schema/profile-root" }
}
```

**Errors**

- `400 invalid_request` — frontmatter fails validation.
- `409 conflict` — `version` is not strictly greater than the current profile root.
- `410 tombstoned` — handle has been tombstoned; re-publish is refused.

---

## `GET /profile/{handle}`

Fetch the mutable profile root. `{handle}` may be passed with or without the leading `@`.

**Response `200`**

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
  "tombstoned": false,
  "tombstone_reason": null
}
```

**Errors**

- `404 not_found` — unknown handle.
- `410 tombstoned` — handle is tombstoned (response body still returned, with `tombstoned: true`).

---

## `GET /cv/{cid}`

Fetch the raw `cv-vN.md` bytes by content ID. Returns `text/markdown`.

**Errors**

- `404 not_found` — CID not pinned by this node.

---

## `POST /search`

Semantic search over profile roots.

**Request**

```json
{
  "query": "staff engineer, rust, distributed systems, EU remote",
  "k": 10,
  "filters": {
    "status": ["open", "passive"],
    "availability": ["looking", "next_available"],
    "min_freshness": 50
  }
}
```

`filters` is optional. Unknown filter keys are ignored within the current version.

**Response `200`**

```json
{
  "hits": [
    {
      "score": 0.82,
      "record": {
        "profile_root": { "...": "..." },
        "cid": "bafy..."
      }
    }
  ]
}
```

---

## `DELETE /profile/{handle}`

Tombstone a handle. Idempotent.

**Request**

```json
{ "reason": "user requested account deletion (GDPR art. 17)" }
```

**Response `200`**

```json
{ "handle": "@ada", "tombstoned": true }
```

---

## Versioning

The HTTP surface is versioned alongside `xtalent/profile-root/vN`. Breaking changes happen under a new prefix (e.g. `/v2/search`) with both live during deprecation.
