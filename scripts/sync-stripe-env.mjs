#!/usr/bin/env node
// Create the Stripe products/prices for the paid plans and write their price ids
// into the repo-root .env — so you never hand-copy a `price_...` id.
//
// Run this once you've put your STRIPE_SECRET_KEY (test- or live-mode) in .env:
//
//   pnpm stripe:seed
//
// It is idempotent: prices are keyed by a stable `lookup_key`, so re-running
// reuses the existing price instead of creating duplicates. It writes only the
// two `STRIPE_PRICE_*` lines (in a managed block) and never touches your
// STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET or prints any secret value.
//
// Requires the Stripe CLI (same prerequisite as `stripe listen`):
//   brew install stripe/stripe-cli/stripe
//
// The mode (test vs live) follows your key: an `sk_test_...` key seeds test-mode
// prices, an `sk_live_...` key seeds live-mode prices. See docs/stripe-setup.md.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const envPath = resolve(root, ".env");

// Paid plans. Amounts (cents) match the plan catalog seeded in
// supabase/migrations/20260708191053_billing_plans_subscriptions.sql so the
// Stripe price and the app's plan tier line up.
const PLANS = [
  { name: "Pro", amount: 1900, lookupKey: "ai_media_pro_monthly", envVar: "STRIPE_PRICE_PRO" },
  { name: "Team", amount: 4900, lookupKey: "ai_media_team_monthly", envVar: "STRIPE_PRICE_TEAM" },
];

function fail(msg) {
  console.error(msg);
  process.exit(1);
}

// --- Read the secret key from .env (never printed) --------------------------
if (!existsSync(envPath)) {
  fail("No .env found. Run `cp .env.example .env` first, then set STRIPE_SECRET_KEY.");
}
const envLines = readFileSync(envPath, "utf8").split("\n");
let secretKey;
for (const line of envLines) {
  const m = line.match(/^STRIPE_SECRET_KEY=(.*)$/);
  if (m) secretKey = m[1].trim().replace(/^"|"$/g, "");
}
if (!secretKey || !/^sk_(test|live)_/.test(secretKey)) {
  fail(
    "STRIPE_SECRET_KEY is missing or not a real key in .env.\n" +
      "Copy your Secret key (sk_test_... or sk_live_...) from the Stripe Dashboard\n" +
      "(Developers -> API keys) into .env, then re-run `pnpm stripe:seed`.\n" +
      "See docs/stripe-setup.md section 3.",
  );
}
const mode = secretKey.startsWith("sk_live_") ? "LIVE" : "test";

// --- Stripe CLI helpers -----------------------------------------------------
function stripe(args) {
  try {
    const out = execFileSync("stripe", [...args, "--api-key", secretKey], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return JSON.parse(out);
  } catch (err) {
    if (err.code === "ENOENT") {
      fail(
        "Stripe CLI not found. Install it, then re-run:\n" +
          "  brew install stripe/stripe-cli/stripe   (see https://docs.stripe.com/stripe-cli)",
      );
    }
    // Stripe CLI prints the API error on stderr; surface it without the key.
    const detail = (err.stderr || err.stdout || err.message || "").toString().trim();
    fail(`Stripe CLI call failed (\`stripe ${args.join(" ")}\`):\n${detail}`);
  }
}

// Reuse an existing recurring price by lookup_key, else create product + price.
function ensurePrice({ name, amount, lookupKey }) {
  const found = stripe(["prices", "list", "--lookup-keys", lookupKey, "--limit", "1"]);
  if (found?.data?.length) return { id: found.data[0].id, created: false };

  const product = stripe(["products", "create", "--name", name]);
  const price = stripe([
    "prices",
    "create",
    "--product",
    product.id,
    "--unit-amount",
    String(amount),
    "--currency",
    "usd",
    "--recurring.interval",
    "month",
    "--lookup-key",
    lookupKey,
  ]);
  return { id: price.id, created: true };
}

console.log(`Seeding Stripe products/prices in ${mode} mode...`);
const results = [];
for (const plan of PLANS) {
  const { id, created } = ensurePrice(plan);
  results.push({ envVar: plan.envVar, id });
  console.log(`  ${plan.name}: ${created ? "created" : "reused"} price for ${plan.envVar}`);
}

// --- Write the managed Stripe-prices block into .env ------------------------
// Strip any prior copy of our block (header + its comment lines + our var lines)
// and any stray managed-var lines, then append a fresh block. This is idempotent
// and removes the WHOLE previous block, not just the var lines (a plain per-line
// filter would orphan the block's comment lines and duplicate them on re-run).
// STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are NOT in `managed`, and other
// managed blocks (e.g. Supabase) are left untouched.
const managed = results.map((r) => r.envVar);
const isManagedVar = (ln) => managed.some((k) => ln.startsWith(k + "="));
const kept = [];
let inBlock = false;
for (const ln of envLines) {
  if (ln.startsWith("# --- Stripe prices")) {
    inBlock = true; // drop the header and the comment lines that follow it
    continue;
  }
  if (inBlock) {
    if (ln.startsWith("#") || ln.trim() === "") continue; // still inside our block
    inBlock = false; // hit a real line -> block is over
  }
  if (isManagedVar(ln)) continue; // our var lines (in-block or a stray/placeholder copy)
  kept.push(ln);
}
while (kept.length && kept[kept.length - 1].trim() === "") kept.pop();

const block = [
  "",
  "# --- Stripe prices (written by `pnpm stripe:seed`) ---",
  "# Account-specific recurring price ids for the paid plans. Regenerate any time",
  "# with `pnpm stripe:seed` (idempotent — keyed by lookup_key).",
  ...results.map((r) => `${r.envVar}=${r.id}`),
];

writeFileSync(envPath, [...kept, ...block].join("\n") + "\n", "utf8");
console.log(`Wrote ${results.length} price ids to .env. Restart \`pnpm dev\` to pick them up.`);
