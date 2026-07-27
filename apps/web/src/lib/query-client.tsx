"use client";

import {
  QueryCache,
  QueryClient,
  QueryClientProvider as TanstackProvider,
} from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { createClient } from "@/lib/supabase/client";
import {
  SIGNIN_REDIRECT_GUARD_KEY,
  shouldRedirectToSignin,
  shouldSignOut,
} from "@/lib/query-helpers";

// When any query 401s, the session is gone (expired/revoked and past Supabase's
// auto-refresh). Bounce to sign-in once instead of leaving the shell filled with
// "Not authorized" states. Only a 401 triggers it (see shouldSignOut) so a
// 402/403/5xx stays an inline error.
//
// Two guards prevent an infinite redirect loop when a *valid* Supabase cookie
// disagrees with an API that rejects the bearer token (a common misconfig:
// mismatched JWT secret / wrong Supabase project). In that case `/signin`'s
// cookie-based middleware would bounce the "authed" user straight back:
//  1. We sign the stale client session out — the root cause — so the middleware
//     stops treating the user as authenticated and can't bounce them back.
//  2. A short sessionStorage-based time window suppresses a second redirect (in
//     case sign-out hasn't propagated yet), so a persistent mismatch surfaces as
//     an inline error instead of a loop. The window self-expires, so a genuine
//     later expiry still redirects.
async function handleGlobalQueryError(error: unknown) {
  if (typeof window === "undefined" || !shouldSignOut(error)) return;
  const { pathname, search } = window.location;
  if (pathname.startsWith("/signin") || pathname.startsWith("/signup")) return;

  const raw = sessionStorage.getItem(SIGNIN_REDIRECT_GUARD_KEY);
  const last = raw ? Number(raw) : null;
  if (!shouldRedirectToSignin(Date.now(), last)) return;
  sessionStorage.setItem(SIGNIN_REDIRECT_GUARD_KEY, String(Date.now()));

  try {
    // scope: "local" clears the cookie the middleware reads WITHOUT a network
    // round-trip to revoke on Supabase — that call could hang in the exact
    // offline/misconfig scenario this guards, delaying the redirect. Local is
    // enough to stop the middleware bounce; the guard covers loop prevention.
    await createClient().auth.signOut({ scope: "local" });
  } catch {
    // Best effort — the time-window guard above still prevents a loop if this
    // fails (e.g. offline).
  }
  const next = encodeURIComponent(pathname + search);
  window.location.assign(`/signin?next=${next}`);
}

// Sane defaults for a B2-backed dashboard:
//  - 30s staleTime — file lists & stats don't change second-to-second; this
//    cuts duplicate fetches across components hitting the same endpoint.
//  - retry: 1 by default, but never retry 4xx — those won't get better on
//    a second try and would just delay the inline ErrorState.
//  - refetchOnWindowFocus stays on (TanStack default) so the dashboard
//    self-heals when the user comes back to the tab.
function makeQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({ onError: handleGlobalQueryError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 1;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function QueryClientProvider({ children }: { children: React.ReactNode }) {
  // Lazy single-instance per browser session. SSR isn't a concern here
  // (dashboard is a client app) but this still avoids re-creating the
  // client on every render.
  const [client] = useState(makeQueryClient);
  return <TanstackProvider client={client}>{children}</TanstackProvider>;
}
