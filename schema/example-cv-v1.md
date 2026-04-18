---
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
location_prefs:
  - remote
  - Amsterdam
skills_matrix:
  - name: rust
    years: 6
    level: expert
  - name: distributed-systems
    years: 5
    level: expert
  - name: observability
    years: 4
    level: advanced
ai_twin_enabled: true
privacy:
  contact:
    handle: "@ada"
  discoverable: true
---

# Ada Lovelace

_Staff software engineer, distributed systems_

## Summary
Builds consensus-heavy systems. Cares about correctness under partition, and
about tests that actually catch the failure modes that ship. Operates equally
well in code, in incident response, and in design review.

## Experience
- **2022–now · Principal Engineer · Nimbus** — Owns the distributed log. Led
  the cutover from single-leader to Raft-backed replication; reduced p99
  write latency by 40% while preserving linearizable reads.
- **2018–2022 · Staff Engineer · Orbit** — Built the control plane that now
  schedules ~20k jobs/min. Author of the incident playbook still in use.
- **2015–2018 · Senior Engineer · Beacon** — Rewrote the ingestion tier in
  Rust; cut memory footprint 6×.

## Projects
- **rustraft** — teaching-grade Raft implementation with property-based
  tests over a simulated network. Used in two university systems courses.
- **obs-kit** — opinionated OpenTelemetry patterns for Rust services.

## Endorsements
_Peer-reviewed on rustraft by @alan: "the property tests are the whole point."_
