import Link from "next/link";
import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SaasStatsCards } from "@/components/dashboard/saas-stats-cards";
import { RecentGenerationsTable } from "@/components/dashboard/recent-generations-table";
import { UploadChart } from "@/components/dashboard/upload-chart";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Your plan, storage, and AI generation activity at a glance.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/generate">
            <Wand2 className="h-3.5 w-3.5" />
            New generation
          </Link>
        </Button>
      </div>
      <SaasStatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <UploadChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentGenerationsTable />
        </div>
      </div>
    </div>
  );
}
