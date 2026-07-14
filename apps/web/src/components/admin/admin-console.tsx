"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OverviewCards } from "@/components/admin/overview-cards";
import {
  AuditGrid,
  FilesGrid,
  JobsGrid,
  ProviderRunsGrid,
  SubscriptionsGrid,
  UsersGrid,
} from "@/components/admin/grids";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "users", label: "Users" },
  { value: "subscriptions", label: "Subscriptions" },
  { value: "jobs", label: "Jobs" },
  { value: "files", label: "Files" },
  { value: "provider", label: "Provider usage" },
  { value: "audit", label: "Audit log" },
];

export function AdminConsole() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Admin</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Every user&apos;s resources across the workspace. Read-only, except role
          changes — which are recorded in the audit log.
        </p>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="flex-wrap">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <OverviewCards />
        </TabsContent>
        <TabsContent value="users">
          <UsersGrid />
        </TabsContent>
        <TabsContent value="subscriptions">
          <SubscriptionsGrid />
        </TabsContent>
        <TabsContent value="jobs">
          <JobsGrid />
        </TabsContent>
        <TabsContent value="files">
          <FilesGrid />
        </TabsContent>
        <TabsContent value="provider">
          <ProviderRunsGrid />
        </TabsContent>
        <TabsContent value="audit">
          <AuditGrid />
        </TabsContent>
      </Tabs>
    </div>
  );
}
