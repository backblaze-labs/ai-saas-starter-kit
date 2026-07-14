"use client";

import type { ColumnDef } from "@tanstack/react-table";
import type { UseQueryResult } from "@tanstack/react-query";

import { DataTable } from "@/components/ui/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import type { ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

/** Truncated monospace cell for long ids / keys. */
export function mono(value: string | null | undefined) {
  return (
    <span className="block max-w-[18ch] truncate font-mono text-xs text-muted-foreground">
      {value || "—"}
    </span>
  );
}

/** Muted, tabular date cell. */
export function dateCell(value: string | null | undefined) {
  return (
    <span className="tabular-nums text-xs text-muted-foreground">
      {value ? formatDate(value) : "—"}
    </span>
  );
}

/** Loading / error / table shell shared by every admin grid. */
export function AdminGrid<T>({
  query,
  columns,
  filterPlaceholder,
  emptyTitle,
}: {
  query: UseQueryResult<T[], ApiError>;
  columns: ColumnDef<T, unknown>[];
  filterPlaceholder?: string;
  emptyTitle?: string;
}) {
  if (query.isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (query.error) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  }
  return (
    <DataTable
      columns={columns}
      data={query.data ?? []}
      filterPlaceholder={filterPlaceholder}
      emptyTitle={emptyTitle ?? "No results"}
    />
  );
}
