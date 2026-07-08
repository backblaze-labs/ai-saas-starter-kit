import { test as setup } from "@playwright/test";
import { createConfirmedUser } from "./helpers/auth-flow";

// Storage-state file consumed by the authenticated project (see playwright.config.ts).
const AUTH_FILE = ".auth/user.json";

setup("sign up, confirm via email, and persist session", async ({ page, request }) => {
  await createConfirmedUser(page, request);
  await page.context().storageState({ path: AUTH_FILE });
});
