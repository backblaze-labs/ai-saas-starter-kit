import crypto from "node:crypto";
import type { APIRequestContext } from "@playwright/test";

// Where the FastAPI backend lives. Matches the web app's NEXT_PUBLIC_API_URL so
// verify runs (which use high ports) can point both at the same instance.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://127.0.0.1:54321";
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

/**
 * Reproduce Stripe's webhook signature scheme (deterministic HMAC-SHA256 over
 * `${timestamp}.${payload}`), so a locally-built event is byte-identical to one
 * Stripe would POST — the backend verifies it for real.
 */
export function stripeSignature(
  payload: string,
  secret: string,
  ts: number = Math.floor(Date.now() / 1000),
): string {
  const mac = crypto.createHmac("sha256", secret).update(`${ts}.${payload}`).digest("hex");
  return `t=${ts},v1=${mac}`;
}

/**
 * Look up a Supabase user id by email via the GoTrue admin API (service role).
 * Uses the auth admin endpoint rather than a `public.profiles` query so it does
 * not depend on public-table grants — the just-created user is newest, so it is
 * on the first page.
 */
export async function lookupUserId(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const res = await request.get(`${SUPABASE_URL}/auth/v1/admin/users?per_page=1000`, {
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
  });
  if (!res.ok()) throw new Error(`admin users lookup failed: ${res.status()}`);
  const body = await res.json();
  const users: Array<{ id: string; email: string }> = body.users ?? body ?? [];
  const match = users.find((u) => u.email === email);
  if (!match) throw new Error(`no user for ${email}`);
  return match.id;
}

/**
 * POST a signed customer.subscription.* event to the live webhook, simulating
 * what Stripe sends after a checkout. The tier is derived from `priceId`, which
 * must match the backend's STRIPE_PRICE_* mapping.
 */
export async function sendSubscriptionWebhook(
  request: APIRequestContext,
  {
    userId,
    priceId,
    secret,
    status = "active",
    eventType = "customer.subscription.updated",
  }: {
    userId: string;
    priceId: string;
    secret: string;
    status?: string;
    eventType?: string;
  },
) {
  const now = Math.floor(Date.now() / 1000);
  const event = {
    id: `evt_e2e_${now}_${Math.floor(Math.random() * 1_000_000)}`,
    object: "event",
    type: eventType,
    data: {
      object: {
        id: `sub_e2e_${now}`,
        object: "subscription",
        customer: `cus_e2e_${now}`,
        status,
        cancel_at_period_end: false,
        metadata: { user_id: userId },
        // basil schema: current_period_end lives on the item, not the top level.
        items: { data: [{ price: { id: priceId }, current_period_end: now + 30 * 86400 }] },
      },
    },
  };
  const body = JSON.stringify(event);
  const sig = stripeSignature(body, secret);
  return request.post(`${API_BASE}/billing/webhook`, {
    headers: { "stripe-signature": sig, "content-type": "application/json" },
    data: body,
  });
}
