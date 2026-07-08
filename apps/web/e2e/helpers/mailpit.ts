import type { APIRequestContext } from "@playwright/test";

// Local Supabase routes all auth emails to Mailpit (default :54324). These helpers
// let e2e tests read those emails, so the full signup -> confirm flow is testable.
const MAILPIT_URL = process.env.MAILPIT_URL || "http://127.0.0.1:54324";

type Poll = { timeoutMs?: number; intervalMs?: number };

async function findMessageId(
  request: APIRequestContext,
  email: string,
): Promise<string | null> {
  const res = await request.get(
    `${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`,
  );
  if (!res.ok()) return null;
  const data = await res.json();
  const messages: Array<{ ID: string }> = data.messages ?? [];
  return messages.length ? messages[0].ID : null;
}

async function messageBody(request: APIRequestContext, id: string): Promise<string> {
  const res = await request.get(`${MAILPIT_URL}/api/v1/message/${id}`);
  if (!res.ok()) return "";
  const body = await res.json();
  return (body.HTML || body.Text || "") as string;
}

/**
 * Poll Mailpit for the most recent email to `email` and return the relative
 * `/auth/confirm?...` path from it (host stripped so the caller can target
 * whatever instance it is testing).
 */
export async function waitForConfirmationPath(
  request: APIRequestContext,
  email: string,
  { timeoutMs = 30_000, intervalMs = 1_000 }: Poll = {},
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const id = await findMessageId(request, email);
    if (id) {
      const html = (await messageBody(request, id)).replace(/&amp;/g, "&");
      const match = html.match(/\/auth\/confirm\?[^"'\s)]+/);
      if (match) return match[0];
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`No confirmation email arrived for ${email} within ${timeoutMs}ms`);
}
