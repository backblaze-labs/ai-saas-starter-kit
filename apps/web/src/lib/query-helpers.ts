import { ApiError } from "@/lib/api-client";

// A minimal view of a TanStack Query result — just the fields the decisions
// below need. Extracting them as pure functions keeps this logic testable in the
// node test env (no jsdom / React render harness required).
export interface QueryLike {
  isError: boolean;
  isPending: boolean;
  data: unknown;
}

export type EntitlementViewState = "loading" | "error" | "ready";

/**
 * How a plan-gated surface (billing, generate) should render based on its
 * entitlements/subscription query.
 *
 * The important case is "error": a transient 500/timeout must NOT be treated as
 * "free/locked". Previously the pages read `entitlements.data?.can_generate ??
 * false`, so any query error silently downgraded a paying user to the locked
 * state with no way to recover but a reload. Returning "error" lets the page
 * render a retry instead.
 */
export function entitlementViewState(query: QueryLike): EntitlementViewState {
  if (query.isError) return "error";
  if (query.isPending || query.data === undefined || query.data === null) return "loading";
  return "ready";
}

/**
 * True when an error means the session is gone and the user should be sent to
 * sign-in. Deliberately narrow — ONLY a 401. A 402 (plan-gated), 403, 404, 5xx,
 * or a network blip must never bounce the user, or normal flows (and Supabase
 * token-refresh races) would trigger spurious sign-outs / redirect loops.
 */
export function shouldSignOut(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

// --- global-401 redirect-loop guard ---------------------------------------

/** sessionStorage key holding the epoch-ms of the last sign-in redirect. */
export const SIGNIN_REDIRECT_GUARD_KEY = "auth:lastSigninRedirect";
/** Suppress a re-redirect within this window (ms). */
export const SIGNIN_REDIRECT_WINDOW_MS = 10_000;

/**
 * Whether a 401 should bounce the user to `/signin`, given the last redirect
 * time. Returns false within the guard window: when a valid Supabase cookie
 * disagrees with an API that rejects the bearer (e.g. mismatched JWT secret or
 * wrong Supabase project), `/signin` bounces the still-"authed" user straight
 * back and the next query 401s again — an infinite loop. The window
 * auto-expires (so a genuine later session expiry still redirects), which also
 * means no explicit "clear on success" is needed. Pure, for testability.
 */
export function shouldRedirectToSignin(
  nowMs: number,
  lastRedirectAtMs: number | null,
): boolean {
  if (lastRedirectAtMs === null) return true;
  return nowMs - lastRedirectAtMs > SIGNIN_REDIRECT_WINDOW_MS;
}

/**
 * True when an error is a plan-gate (402) rather than a real failure. A Free
 * user hitting a Pro-only probe should see the locked state; any OTHER error
 * (500/timeout/network) must show a retry, not the misleading "locked" copy.
 */
export function isPlanGated(error: unknown): boolean {
  return error instanceof ApiError && error.status === 402;
}
