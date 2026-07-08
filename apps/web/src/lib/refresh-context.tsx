"use client";

import { createContext, useCallback, useContext } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/queries";

interface RefreshContextValue {
  /** Re-fetch every B2-backed query (files, stats, activity, previews). */
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
    qc.invalidateQueries({ queryKey: qk.all });
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
