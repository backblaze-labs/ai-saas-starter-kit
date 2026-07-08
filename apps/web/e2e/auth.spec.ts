import { test, expect } from "@playwright/test";
import { createConfirmedUser } from "./helpers/auth-flow";

test.describe("unauthenticated", () => {
  // Reset the stored session so these run without auth.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("dashboard redirects to /signin", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/signin/);
  });

  test("a protected route redirects to /signin with a next param", async ({ page }) => {
    await page.goto("/files");
    await expect(page).toHaveURL(/\/signin\?next=/);
  });

  test("the sign-in screen offers password and email-code methods", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByRole("tab", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Email code" })).toBeVisible();
  });
});

// These share the persisted session (setup project). They are read-only w.r.t.
// the session, so they never invalidate it for one another.
test.describe("authenticated", () => {
  test("reaches the protected dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page).not.toHaveURL(/signin/);
    // Authenticated shell rendered: the sidebar sign-out control is present.
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  });

  test("/dashboard aliases to the dashboard home", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/localhost(:\d+)?\/$/);
    await expect(page).not.toHaveURL(/signin/);
  });

  test("account page validates the session against the API", async ({ page }) => {
    await page.goto("/account");
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    await expect(page.getByText(/Authenticated to the API as/)).toBeVisible();
  });
});

// Sign-out mutates the session, so it uses its own fresh user rather than the
// shared one (keeps the read-only tests above isolated).
test.describe("sign out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("returns to /signin", async ({ page, request }) => {
    await createConfirmedUser(page, request);
    await page.goto("/account");
    await page.getByRole("button", { name: "Sign out" }).last().click();
    await expect(page).toHaveURL(/\/signin/);
  });
});
