import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { waitForConfirmationPath } from "./mailpit";

const PASSWORD = "Passw0rd!123";

/**
 * Sign up a fresh, unique user and complete email confirmation via Mailpit,
 * leaving `page` authenticated. Each call uses a unique email so tests that
 * mutate the session (e.g. sign out) stay isolated from one another.
 */
export async function createConfirmedUser(
  page: Page,
  request: APIRequestContext,
): Promise<{ email: string; password: string }> {
  const email = `verify_b1_${Date.now()}_${Math.floor(Math.random() * 1_000_000)}@example.com`;

  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Verify B1");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Check your email")).toBeVisible();

  const confirmPath = await waitForConfirmationPath(request, email);
  await page.goto(confirmPath);
  await expect(page).not.toHaveURL(/signin/);

  return { email, password: PASSWORD };
}
