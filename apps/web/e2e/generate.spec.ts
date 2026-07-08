import { test, expect } from "@playwright/test";
import { createConfirmedUser } from "./helpers/auth-flow";
import { lookupUserId, sendSubscriptionWebhook } from "./helpers/stripe-webhook";

const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const NVIDIA_KEY = process.env.NVIDIA_API_KEY;
const PRICE_PRO = process.env.STRIPE_PRICE_PRO || "price_pro_local_e2e";

// Read-only against the shared persisted session (setup project) — a fresh user
// with no subscription, i.e. the Free tier. Generation is Pro-gated.
test.describe("generate", () => {
  test("appears in the sidebar navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Generate" })).toBeVisible();
  });

  test("gates generation for a Free user", async ({ page }) => {
    await page.goto("/generate");
    await expect(page.getByRole("heading", { name: "Generate" })).toBeVisible();
    // A Free user hits the same require_plan("pro") gate the backend enforces.
    await expect(page.getByTestId("generate-locked")).toBeVisible();
    await expect(page.getByTestId("generate-form")).toHaveCount(0);
  });
});

// The full text-to-image flow: upgrade a fresh user to Pro via a real signed
// webhook, then generate an image and confirm it renders. Needs Stripe webhook
// + Supabase service-role config (to upgrade) AND a live NVIDIA_API_KEY (to
// actually generate); skips cleanly otherwise — Phase D covers it manually.
test.describe("generation flow (Pro + NVIDIA)", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a Pro user generates an image that lands in B2", async ({ page, request }) => {
    test.skip(
      !WEBHOOK_SECRET || !SERVICE_KEY || !NVIDIA_KEY,
      "requires STRIPE_WEBHOOK_SECRET + SUPABASE_SERVICE_ROLE_KEY + NVIDIA_API_KEY",
    );

    const { email } = await createConfirmedUser(page, request);
    const userId = await lookupUserId(request, email);
    const resp = await sendSubscriptionWebhook(request, {
      userId,
      priceId: PRICE_PRO,
      secret: WEBHOOK_SECRET as string,
    });
    expect(resp.ok(), `webhook POST failed: ${resp.status()}`).toBeTruthy();

    await page.goto("/generate");
    // Now on Pro: the form is available (no locked card).
    await expect(page.getByTestId("generate-form")).toBeVisible();
    await expect(page.getByTestId("generate-locked")).toHaveCount(0);

    await page.getByTestId("generate-prompt").fill("a single red apple on a white studio background");
    await page.getByTestId("generate-submit").click();

    // flux.1-schnell + B2 upload — allow generous wall-clock.
    await expect(page.getByTestId("generate-result")).toBeVisible({ timeout: 120_000 });
    await expect(page.getByTestId("generate-result").locator("img").first()).toBeVisible();
  });
});
