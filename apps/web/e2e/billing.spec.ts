import { test, expect } from "@playwright/test";
import { createConfirmedUser } from "./helpers/auth-flow";
import { lookupUserId, sendSubscriptionWebhook } from "./helpers/stripe-webhook";

const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const PRICE_PRO = process.env.STRIPE_PRICE_PRO || "price_pro_local_e2e";

// Read-only against the shared persisted session (setup project) — a fresh user
// with no subscription, i.e. the Free tier.
test.describe("billing", () => {
  test("shows the plan catalog and the current (Free) plan", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible();
    await expect(page.getByTestId("plan-card-free")).toBeVisible();
    await expect(page.getByTestId("plan-card-pro")).toBeVisible();
    await expect(page.getByTestId("plan-card-team")).toBeVisible();
    await expect(page.getByTestId("current-plan")).toHaveText("FREE");
  });

  test("gates Pro features for a Free user", async ({ page }) => {
    await page.goto("/billing");
    // The Pro-preview card calls the same require_plan("pro") gate the backend
    // enforces; a Free user sees the locked state (402 under the hood).
    await expect(page.getByTestId("pro-preview-locked")).toBeVisible();
    await expect(page.getByTestId("pro-preview-unlocked")).toHaveCount(0);
  });

  test("appears in the sidebar navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Billing" })).toBeVisible();
  });
});

// The end-to-end billing flow drives a real Stripe-signed webhook against the
// live backend (no Stripe account needed — the signature is byte-identical).
// Needs STRIPE_WEBHOOK_SECRET (so the backend accepts the signature) and
// SUPABASE_SERVICE_ROLE_KEY (to resolve the user id); skips cleanly otherwise.
test.describe("billing upgrade via webhook", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a subscription webhook upgrades the user and unlocks Pro", async ({
    page,
    request,
  }) => {
    test.skip(
      !WEBHOOK_SECRET || !SERVICE_KEY,
      "requires STRIPE_WEBHOOK_SECRET + SUPABASE_SERVICE_ROLE_KEY",
    );

    const { email } = await createConfirmedUser(page, request);
    await page.goto("/billing");
    await expect(page.getByTestId("pro-preview-locked")).toBeVisible();

    const userId = await lookupUserId(request, email);
    const resp = await sendSubscriptionWebhook(request, {
      userId,
      priceId: PRICE_PRO,
      secret: WEBHOOK_SECRET as string,
    });
    expect(resp.ok(), `webhook POST failed: ${resp.status()}`).toBeTruthy();
    expect((await resp.json()).status).toBe("processed");

    // Reload so TanStack Query refetches the now-synced subscription state.
    await page.reload();
    await expect(page.getByTestId("current-plan")).toHaveText("PRO");
    await expect(page.getByTestId("pro-preview-unlocked")).toBeVisible();
  });
});
