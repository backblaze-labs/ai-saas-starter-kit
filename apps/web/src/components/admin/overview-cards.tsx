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

  const metrics: { label: string; value: string | number }[] = data
    ? [
        { label: "Users", value: data.users },
        { label: "Admins", value: data.admins },
        { label: "Active subscriptions", value: data.active_subscriptions },
        { label: "Generation jobs", value: data.generation_jobs },
        { label: "Failed jobs", value: data.failed_jobs },
        { label: "Generated files", value: data.files },
        { label: "Storage used", value: humanizeBytes(data.storage_bytes) },
        { label: "Provider runs", value: data.provider_runs },
        { label: "Webhook events", value: data.webhook_events },
      ]
    : Array.from({ length: 9 }).map((_, i) => ({ label: `m${i}`, value: 0 }));

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
