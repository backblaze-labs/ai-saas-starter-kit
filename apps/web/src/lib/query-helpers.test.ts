import { describe, expect, it } from "vitest";
import { ApiError } from "./api-client";
import { entitlementViewState, shouldSignOut } from "./query-helpers";

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
