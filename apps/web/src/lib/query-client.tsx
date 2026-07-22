"use client";

import {
  QueryCache,
  QueryClient,
  QueryClientProvider as TanstackProvider,
} from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";
import { shouldSignOut } from "@/lib/query-helpers";

// When any query 401s, the session is gone (expired/revoked and past Supabase's
// auto-refresh). Bounce to sign-in once instead of leaving the shell filled with
// "Not authorized" states. Guarded so we never redirect-loop from the auth pages
// themselves, and only a 401 triggers it (see shouldSignOut) so a 402/403/5xx
// stays an inline error.
function handleGlobalQueryError(error: unknown) {
  if (typeof window === "undefined" || !shouldSignOut(error)) return;
  const { pathname, search } = window.location;
  if (pathname.startsWith("/signin") || pathname.startsWith("/signup")) return;
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
