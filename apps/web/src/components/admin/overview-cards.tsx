"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { useAdminOverview } from "@/lib/queries";
import { humanizeBytes } from "@/lib/utils";

export function OverviewCards() {
  const { data, isLoading, error, refetch } = useAdminOverview();

  if (error) {
    return <ErrorState error={error} onRetry={() => refetch()} />;
  }

  // Labels are static so they render correctly during the loading state (the
  // value cell shows a skeleton until data arrives) instead of placeholders.
  const metrics: { label: string; value: string | number }[] = [
    { label: "Users", value: data?.users ?? 0 },
    { label: "Admins", value: data?.admins ?? 0 },
    { label: "Active subscriptions", value: data?.active_subscriptions ?? 0 },
    { label: "Generation jobs", value: data?.generation_jobs ?? 0 },
    { label: "Failed jobs", value: data?.failed_jobs ?? 0 },
    { label: "Generated files", value: data?.files ?? 0 },
    {
      label: "Storage used",
      value: data ? humanizeBytes(data.storage_bytes) : "—",
    },
    { label: "Provider runs", value: data?.provider_runs ?? 0 },
    { label: "Webhook events", value: data?.webhook_events ?? 0 },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {metrics.map((m) => (
        <Card key={m.label} className="card-hover">
          <CardHeader className="pt-4 pb-2 px-4">
            <CardTitle className="text-xs font-semibold text-muted-foreground">
              {m.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-5 px-4">
            {isLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <div className="stat-value">{m.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
