/**
 * Protocol types for xTalent Graph.
 *
 * These mirror the Pydantic models in `python/src/xtalent/core.py` and the
 * request/response shapes documented in `docs/api.md`. Field names and
 * semantics are authoritative on the server; the client must not rename
 * them.
 */

/** RFC3339 UTC timestamp, e.g. `"2026-04-18T11:02:00Z"`. */
export type ISODateString = string;

/** Content identifier returned by the publisher. CIDv1-shaped (starts with `bafy`). */
export type CID = string;

/** `@handle` form. Matches `^@[\w]+$`. */
export type Handle = string;

export const CV_SCHEMA_ID = "xtalent/cv/v1" as const;
export const PROFILE_ROOT_SCHEMA_ID = "xtalent/profile-root/v1" as const;

export type Status = "open" | "passive" | "closed" | "hired" | "inactive";
export type Availability = "looking" | "not_looking" | "next_available";

export interface SkillEntry {
  name: string;
  years?: number;
  level?: "beginner" | "intermediate" | "advanced" | "expert" | string;
  [key: string]: unknown;
}

export interface SalaryExpectation {
  currency: string;
  min?: number;
  max?: number;
  [key: string]: unknown;
}

export interface PrivacyBlock {
  contact?: { handle?: Handle; email?: string; [key: string]: unknown };
  discoverable?: boolean;
  [key: string]: unknown;
}

/**
 * Immutable CV document, schema `xtalent/cv/v1`.
 * When serialized to Markdown, these frontmatter fields are followed by
 * required `## Summary`, `## Experience`, `## Projects` sections (plus
 * optional `## Endorsements`).
 */
export interface XTalentCV {
  schema: typeof CV_SCHEMA_ID;
  handle: Handle;
  version: number;
  last_updated: ISODateString;
  status: Status;
  availability: Availability;
  next_available_date?: ISODateString | null;
  expires_at?: ISODateString | null;
  freshness_score: number;
  salary_expectation?: SalaryExpectation | null;
  location_prefs: string[];
  skills_matrix: SkillEntry[];
  ai_twin_enabled: boolean;
  privacy: PrivacyBlock;
  full_name: string;
  title: string;
  summary: string;
  experience: string;
  projects: string;
  endorsements: string;
}

/**
 * Mutable pointer document, schema `xtalent/profile-root/v1`.
 * The only part of the protocol that changes over time.
 */
export interface ProfileRoot {
  schema: typeof PROFILE_ROOT_SCHEMA_ID;
  handle: Handle;
  latest_cid: CID;
  version: number;
  status: Status;
  availability: Availability;
  next_available_date?: ISODateString | null;
  freshness_score: number;
  updated_at: ISODateString;
  tombstoned: boolean;
  tombstone_reason?: string | null;
}

export interface SearchFilters {
  status?: Status[];
  availability?: Availability[];
  min_freshness?: number;
  include_tombstoned?: boolean;
}

export interface SearchRequest {
  query: string;
  k?: number;
  filters?: SearchFilters;
}

export interface IndexedRecord {
  profile_root: ProfileRoot;
  cid: CID;
}

export interface SearchHit {
  score: number;
  record: IndexedRecord;
}

export interface SearchResponse {
  hits: SearchHit[];
}

export interface PublishResponse {
  handle: Handle;
  cid: CID;
  profile_root: ProfileRoot;
}

export interface TombstoneResponse {
  handle: Handle;
  tombstoned: boolean;
}

export interface ProtocolErrorBody {
  error: {
    code: "not_found" | "invalid_request" | "conflict" | "tombstoned" | string;
    message: string;
    details?: Record<string, unknown>;
  };
}
