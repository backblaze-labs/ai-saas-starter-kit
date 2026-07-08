#!/usr/bin/env node
// Sync the local Supabase block in the repo-root .env from `supabase status`.
//
// Run this after `supabase start` so the app picks up your local Supabase URL and
// keys. It is idempotent (replaces any prior Supabase-managed lines) and never
// prints secret values. For a HOSTED Supabase project you do NOT need this script —
// just set the five NEXT_PUBLIC_SUPABASE_*/SUPABASE_* vars in .env by hand.
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const envPath = resolve(root, ".env");

let raw;
try {
  raw = execSync("supabase status -o env", {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  });
} catch {
  console.error(
    "Could not read `supabase status`. Is the local stack running? Try `supabase start`.",
  );
  process.exit(1);
}

const vars = {};
for (const line of raw.split("\n")) {
  const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
  if (m) vars[m[1]] = m[2].replace(/^"|"$/g, "");
}
const apiUrl = vars.API_URL;
const anon = vars.ANON_KEY;
const service = vars.SERVICE_ROLE_KEY;
if (!apiUrl || !anon || !service) {
  console.error("`supabase status` did not yield API_URL / ANON_KEY / SERVICE_ROLE_KEY.");
  process.exit(1);
}

const managed = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "SUPABASE_URL",
  "SUPABASE_ANON_KEY",
  "SUPABASE_SERVICE_ROLE_KEY",
];

const existing = existsSync(envPath) ? readFileSync(envPath, "utf8").split("\n") : [];
const kept = existing.filter(
  (ln) => !managed.some((k) => ln.startsWith(k + "=")) && !ln.startsWith("# --- Supabase"),
);
while (kept.length && kept[kept.length - 1].trim() === "") kept.pop();

const block = [
  "",
  "# --- Supabase (auth + Postgres) ---",
  "# LOCAL values written by `node scripts/sync-supabase-env.mjs` from `supabase status`.",
  "# For a HOSTED project, replace all five with your project's values (Project Settings -> API).",
  "# Frontend (Next.js, browser-exposed):",
  `NEXT_PUBLIC_SUPABASE_URL=${apiUrl}`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY=${anon}`,
  "# Backend (FastAPI, server-only; never expose the service-role key to the browser):",
  `SUPABASE_URL=${apiUrl}`,
  `SUPABASE_ANON_KEY=${anon}`,
  `SUPABASE_SERVICE_ROLE_KEY=${service}`,
];

writeFileSync(envPath, [...kept, ...block].join("\n") + "\n", "utf8");
console.log(`Wrote Supabase block to .env (${managed.length} vars). Values not printed.`);
