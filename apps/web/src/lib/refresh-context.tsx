"use client";

import { createContext, useCallback, useContext } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { invalidateFileData } from "@/lib/queries";

interface RefreshContextValue {
  /** Re-fetch the B2-backed file queries (file lists, stats, activity) — e.g.
   *  after an upload. Scoped to file data so it doesn't churn unrelated caches
   *  (health, entitlements) or re-request every open preview URL. */
  triggerRefresh: () => void;
  /** Kept for backwards compatibility with existing call sites. With
   *  TanStack Query in place, components should prefer `useQuery`'s own
   *  `refetch()` or scoped `queryClient.invalidateQueries({ queryKey })`. */
  refreshKey: number;
}

const RefreshContext = createContext<RefreshContextValue>({
  triggerRefresh: () => {},
  refreshKey: 0,
});

export function RefreshProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const triggerRefresh = useCallback(() => {
    invalidateFileData(qc);
  }, [qc]);

  return (
    <RefreshContext.Provider value={{ triggerRefresh, refreshKey: 0 }}>
      {children}
    </RefreshContext.Provider>
  );
}

export function useRefresh() {
  return useContext(RefreshContext);
}
