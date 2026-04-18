/**
 * End-to-end TypeScript demo. Expects a running reference server:
 *   cd ../python && uvicorn xtalent.api:app --reload
 *   cd ../typescript && npm install
 *   npx tsx ../examples/demo.ts
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { XTalentClient } from "../typescript/src/index.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cvMarkdown = readFileSync(resolve(__dirname, "../schema/example-cv-v1.md"), "utf-8");

async function main(): Promise<void> {
  const client = new XTalentClient({
    baseUrl: process.env.XTALENT_URL ?? "http://localhost:8000",
  });

  const published = await client.publish(cvMarkdown);
  console.log(
    `published ${published.handle} v${published.profile_root.version} → ${published.cid}`,
  );

  const profile = await client.getProfile(published.handle);
  console.log(
    `profile: status=${profile.status} availability=${profile.availability} freshness=${profile.freshness_score}`,
  );

  const results = await client.search({
    query: "staff engineer, rust, distributed systems",
    k: 5,
    filters: { availability: ["looking", "next_available"], min_freshness: 50 },
  });

  for (const hit of results.hits) {
    console.log(
      `  ${hit.record.profile_root.handle}  ${hit.score.toFixed(3)}  cid=${hit.record.cid}`,
    );
  }
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
