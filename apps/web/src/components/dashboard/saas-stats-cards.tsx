"use client";

import type { ReactNode } from "react";
import { AlertTriangle, CreditCard, HardDrive, Sparkles } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { useFileStats, useGenerationJobs, useSubscription } from "@/lib/queries";

function StatCard({
  title,
  icon: Icon,
  loading,
  children,
  stagger,
}: {
  title: string;
  icon: typeof CreditCard;
  loading: boolean;
  children: ReactNode;
  stagger: number;
}) {
  return (
    <Card className={`card-hover animate-fade-in-up stagger-${stagger}`}>
      <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
        <CardTitle className="text-xs font-semibold text-muted-foreground">
          {title}
        </CardTitle>
        <div className="stat-icon-wrap">
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent className="pb-5 px-4">
        {loading ? <Skeleton className="h-8 w-24" /> : children}
      </CardContent>
    </Card>
  );
}

/**
 * SaaS dashboard KPIs: plan + status, storage used, generations produced, and
 * failed jobs. Composed from the existing billing / storage / generation query
 * hooks — no dashboard-specific endpoint needed.
 */
export function SaasStatsCards() {
  const sub = useSubscription();
  const stats = useFileStats();
  const jobs = useGenerationJobs();

  const jobList = jobs.data ?? [];
  const succeeded = jobList.filter((j) => j.status === "succeeded").length;
  const failed = jobList.filter((j) => j.status === "failed").length;
  const planName = (sub.data?.plan_id ?? "free").toUpperCase();

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard title="Plan" icon={CreditCard} loading={sub.isLoading} stagger={1}>
        <div className="flex items-center gap-2">
          <span className="stat-value">{planName}</span>
          {sub.data && <StatusBadge status={sub.data.status} />}
        </div>
      </StatCard>

      <StatCard title="Storage used" icon={HardDrive} loading={stats.isLoading} stagger={2}>
        <div className="stat-value">{stats.data?.total_size_human ?? "0 B"}</div>
      </StatCard>

      <StatCard title="Generations" icon={Sparkles} loading={jobs.isLoading} stagger={3}>
        <div className="stat-value">{succeeded}</div>
      </StatCard>

      <StatCard title="Failed generations" icon={AlertTriangle} loading={jobs.isLoading} stagger={4}>
        <div className="stat-value">{failed}</div>
      </StatCard>
    </div>
  );
}
