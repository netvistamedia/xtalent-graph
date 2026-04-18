/**
 * xTalent Graph TypeScript SDK.
 *
 * A thin, typed HTTP client over the reference FastAPI server described in
 * `docs/api.md`. The SDK is transport-only: it does not parse CV Markdown or
 * hold any cache state. Drop in your own `fetch` for testing or for
 * instrumented transports.
 */

import type {
  Handle,
  ProfileRoot,
  ProtocolErrorBody,
  PublishResponse,
  SearchRequest,
  SearchResponse,
  TombstoneResponse,
} from "./types.js";

export * from "./types.js";

/** Fetch-compatible callable. Matches the built-in global in Node 20+ and browsers. */
export type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export interface XTalentClientOptions {
  /** Base URL of an xTalent Graph server, e.g. `http://localhost:8000`. */
  baseUrl: string;
  /** Optional bearer token. If set, sent as `Authorization: Bearer <token>`. */
  apiKey?: string;
  /** Override the global `fetch`. Useful for tests, SSR, or instrumentation. */
  fetch?: FetchLike;
  /** Per-request timeout in milliseconds. Default: 15000. */
  timeoutMs?: number;
}

/**
 * Raised when the server returns a non-2xx response with a protocol-shaped
 * error body. `code` mirrors `docs/api.md`.
 */
export class XTalentError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;

  constructor(status: number, body: ProtocolErrorBody) {
    super(`${body.error.code}: ${body.error.message}`);
    this.name = "XTalentError";
    this.status = status;
    this.code = body.error.code;
    this.details = body.error.details;
  }
}

/** Typed client for the xTalent Graph HTTP surface. */
export class XTalentClient {
  private readonly baseUrl: string;
  private readonly apiKey: string | undefined;
  private readonly fetchImpl: FetchLike;
  private readonly timeoutMs: number;

  constructor(options: XTalentClientOptions) {
    if (!options.baseUrl) throw new Error("baseUrl is required");
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  /** Pin a new CV version and update the profile root. */
  async publish(cvMarkdown: string): Promise<PublishResponse> {
    return this.request<PublishResponse>("POST", "/publish", { cv_markdown: cvMarkdown });
  }

  /** Fetch the mutable profile root for a handle. */
  async getProfile(handle: Handle | string): Promise<ProfileRoot> {
    return this.request<ProfileRoot>("GET", `/profile/${encodeURIComponent(handle)}`);
  }

  /** Fetch the raw `cv-vN.md` bytes by CID. Returns the Markdown string. */
  async getCV(cid: string): Promise<string> {
    const res = await this.raw("GET", `/cv/${encodeURIComponent(cid)}`);
    if (!res.ok) throw await this.toError(res);
    return res.text();
  }

  /** Semantic search over profile roots. */
  async search(req: SearchRequest): Promise<SearchResponse> {
    return this.request<SearchResponse>("POST", "/search", req);
  }

  /** Tombstone a handle (GDPR-style withdrawal). Idempotent. */
  async tombstone(handle: Handle | string, reason?: string): Promise<TombstoneResponse> {
    const body = reason === undefined ? {} : { reason };
    return this.request<TombstoneResponse>(
      "DELETE",
      `/profile/${encodeURIComponent(handle)}`,
      body,
    );
  }

  // ---------------------------------------------------------------------
  // Internals
  // ---------------------------------------------------------------------

  private async request<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<T> {
    const res = await this.raw(method, path, body);
    if (!res.ok) throw await this.toError(res);
    return (await res.json()) as T;
  }

  private async raw(
    method: "GET" | "POST" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.apiKey) headers["Authorization"] = `Bearer ${this.apiKey}`;

    const init: RequestInit = { method, headers };
    if (body !== undefined && method !== "GET") {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    init.signal = controller.signal;

    try {
      return await this.fetchImpl(`${this.baseUrl}${path}`, init);
    } finally {
      clearTimeout(timer);
    }
  }

  private async toError(res: Response): Promise<XTalentError> {
    let body: ProtocolErrorBody;
    try {
      const parsed = (await res.json()) as { detail?: ProtocolErrorBody } | ProtocolErrorBody;
      body = "detail" in parsed && parsed.detail ? parsed.detail : (parsed as ProtocolErrorBody);
    } catch {
      body = {
        error: {
          code: res.status === 404 ? "not_found" : "invalid_request",
          message: res.statusText || `HTTP ${res.status}`,
        },
      };
    }
    return new XTalentError(res.status, body);
  }
}
