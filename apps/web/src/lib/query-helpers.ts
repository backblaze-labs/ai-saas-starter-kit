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
