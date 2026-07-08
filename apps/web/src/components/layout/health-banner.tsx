"use client";

import { AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api-client";

interface HealthResponse {
  status: "healthy" | "degraded";
  b2_connected: boolean;
}

// 5s timeout — long enough for a sleepy dev API to respond, short enough
// that a hung backend doesn't keep the banner ambiguous for 30 seconds.
async function fetchHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return null;
    return (await res.json()) as HealthResponse;
  } catch {
    // API is down. The per-component <ErrorState> will explain that;
    // returning null here keeps the banner silent rather than stacking
    // two error surfaces.
    return null;
  }
}

/**
 * Shows a top-of-app warning when the API is up but B2 itself is
 * misconfigured (`b2_connected: false`) — the case where individual
 * fetches succeed (returning empty/stale data) and the per-component
 * ErrorState would never fire. Polls every 60s and on window focus.
 */
export function HealthBanner() {
  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  });

  if (!data || data.b2_connected) return null;

  return (
    <div
      role="alert"
      className="flex items-center gap-2 border-b border-[color-mix(in_oklab,var(--attention)_30%,var(--border))] bg-[var(--attention-subtle)] px-4 py-2 text-xs text-[var(--attention)]"
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span className="font-medium">B2 not connected.</span>
      <span className="text-foreground/70">
        The API is running but can&apos;t reach Backblaze. Check your{" "}
        <code className="font-mono text-[11px]">.env</code> credentials and
        bucket region, then restart the API.
      </span>
    </div>
  );
}
