/**
 * End-to-end example: publish a CV and search it back.
 *
 * Run:
 *   npm install
 *   # in a separate shell, from ../python:
 *   uvicorn xtalent.api:app --reload
 *   # then:
 *   npx tsx example.ts
 */

import { XTalentClient, XTalentError } from "./src/index.js";

const SAMPLE_CV = `---
schema: xtalent/cv/v1
handle: "@ada"
version: 1
last_updated: 2026-04-18T09:00:00Z
status: open
availability: looking
next_available_date: null
expires_at: null
freshness_score: 96
salary_expectation:
  currency: EUR
  min: 120000
  max: 160000
location_prefs: [remote, Amsterdam]
skills_matrix:
  - name: rust
    years: 6
    level: expert
  - name: distributed-systems
    years: 5
    level: expert
ai_twin_enabled: true
privacy:
  contact:
    handle: "@ada"
  discoverable: true
---

# Ada Lovelace

_Staff software engineer, distributed systems_

## Summary
Builds consensus-heavy systems. Cares about correctness under partition.

## Experience
- 2022–now: Principal at Nimbus (distributed log).
- 2018–2022: Staff at Orbit.

## Projects
- rustraft: a teaching raft implementation.
- obs-kit: OpenTelemetry patterns.

## Endorsements
_Peer-reviewed on rustraft by @alan._
`;

async function main(): Promise<void> {
  const client = new XTalentClient({
    baseUrl: process.env.XTALENT_URL ?? "http://localhost:8000",
  });

  try {
    const published = await client.publish(SAMPLE_CV);
    console.log("published", {
      handle: published.handle,
      cid: published.profile_root.latest_cid,
      version: published.profile_root.version,
    });

    const results = await client.search({
      query: "staff engineer, rust, distributed systems",
      k: 5,
    });
    for (const hit of results.hits) {
      console.log(
        "hit",
        hit.score.toFixed(3),
        hit.record.profile_root.handle,
        hit.record.cid,
      );
    }
  } catch (err) {
    if (err instanceof XTalentError) {
      console.error(`xtalent error: [${err.status}] ${err.code}: ${err.message}`);
      process.exit(1);
    }
    throw err;
  }
}

main();
