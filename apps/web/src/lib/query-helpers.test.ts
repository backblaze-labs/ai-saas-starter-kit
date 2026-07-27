import { describe, expect, it } from "vitest";
import { ApiError } from "./api-client";
import {
  entitlementViewState,
  isPlanGated,
  SIGNIN_REDIRECT_WINDOW_MS,
  shouldRedirectToSignin,
  shouldSignOut,
} from "./query-helpers";

describe("entitlementViewState", () => {
  it("is 'error' when the query errored — never silently 'free'/locked", () => {
    // The bug this guards: a transient failure must not downgrade a paying user.
    expect(
      entitlementViewState({ isError: true, isPending: false, data: undefined }),
    ).toBe("error");
    // isError wins even if stale data lingers.
    expect(
      entitlementViewState({ isError: true, isPending: false, data: { tier: "pro" } }),
    ).toBe("error");
  });

  it("is 'loading' while pending or before data arrives", () => {
    expect(
      entitlementViewState({ isError: false, isPending: true, data: undefined }),
    ).toBe("loading");
    expect(
      entitlementViewState({ isError: false, isPending: false, data: null }),
    ).toBe("loading");
  });

  it("is 'ready' once data is present without error", () => {
    expect(
      entitlementViewState({ isError: false, isPending: false, data: { tier: "pro" } }),
    ).toBe("ready");
  });
});

describe("shouldSignOut", () => {
  it("is true only for a 401", () => {
    expect(shouldSignOut(new ApiError("unauthorized", 401))).toBe(true);
  });

  it("is false for other statuses that must not bounce the user", () => {
    for (const status of [402, 403, 404, 429, 500, 503, 0]) {
      expect(shouldSignOut(new ApiError("x", status))).toBe(false);
    }
  });

  it("is false for non-ApiError errors", () => {
    expect(shouldSignOut(new Error("network"))).toBe(false);
    expect(shouldSignOut(null)).toBe(false);
  });
});

describe("shouldRedirectToSignin", () => {
  it("redirects when no prior redirect is recorded", () => {
    expect(shouldRedirectToSignin(1_000_000, null)).toBe(true);
  });

  it("does NOT redirect again within the guard window (breaks the loop)", () => {
    const now = 1_000_000;
    expect(shouldRedirectToSignin(now, now)).toBe(false);
    expect(shouldRedirectToSignin(now + SIGNIN_REDIRECT_WINDOW_MS, now)).toBe(false);
  });

  it("redirects again once the window has elapsed (self-healing)", () => {
    const last = 1_000_000;
    expect(shouldRedirectToSignin(last + SIGNIN_REDIRECT_WINDOW_MS + 1, last)).toBe(true);
  });
});

describe("isPlanGated", () => {
  it("is true only for a 402 (locked, not a failure)", () => {
    expect(isPlanGated(new ApiError("payment required", 402))).toBe(true);
  });

  it("is false for real failures that must show a retry, not 'locked'", () => {
    for (const status of [401, 403, 500, 503, 0]) {
      expect(isPlanGated(new ApiError("x", status))).toBe(false);
    }
    expect(isPlanGated(new Error("boom"))).toBe(false);
  });
});
