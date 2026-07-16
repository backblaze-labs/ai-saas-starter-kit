"use client";

import type { ColumnDef } from "@tanstack/react-table";

import type {
  AdminAuditEvent,
  AdminFile,
  AdminProviderRun,
  AdminUser,
  GenerationJob,
  Role,
  Subscription,
} from "@ai-saas-starter-kit/shared";
import { StatusBadge } from "@/components/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/components/auth/auth-provider";
import {
  useAdminAudit,
  useAdminFiles,
  useAdminJobs,
  useAdminProviderRuns,
  useAdminSubscriptions,
  useAdminUsers,
  useSetUserRole,
} from "@/lib/queries";
import { humanizeBytes } from "@/lib/utils";
import { AdminGrid, dateCell, mono } from "@/components/admin/grid-helpers";

// --- users (with audited role change) --------------------------------------

export function UsersGrid() {
  const query = useAdminUsers();
  const setRole = useSetUserRole();
  const { user } = useAuth();
  const selfId = user?.id;

  const columns: ColumnDef<AdminUser, unknown>[] = [
    {
      accessorKey: "email",
      header: "Email",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.email || "—"}</span>
      ),
    },
    {
      accessorKey: "full_name",
      header: "Name",
      cell: ({ row }) => row.original.full_name || "—",
    },
    {
      accessorKey: "role",
      header: "Role",
      size: 150,
      cell: ({ row }) => {
        const u = row.original;
        const isSelf = u.id === selfId;
        return (
          <Select
            value={u.role}
            disabled={isSelf || setRole.isPending}
            onValueChange={(v) => setRole.mutate({ userId: u.id, role: v as Role })}
          >
            <SelectTrigger className="h-7 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="user">user</SelectItem>
              <SelectItem value="admin">admin</SelectItem>
            </SelectContent>
          </Select>
        );
      },
    },
    {
      accessorKey: "created_at",
      header: "Joined",
      cell: ({ row }) => dateCell(row.original.created_at),
    },
  ];

  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by email…"
      emptyTitle="No users"
    />
  );
}

// --- subscriptions ---------------------------------------------------------

export function SubscriptionsGrid() {
  const query = useAdminSubscriptions();
  const columns: ColumnDef<Subscription, unknown>[] = [
    { accessorKey: "user_id", header: "User", cell: ({ row }) => mono(row.original.user_id) },
    {
      accessorKey: "plan_id",
      header: "Plan",
      cell: ({ row }) => <span className="uppercase">{row.original.plan_id}</span>,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      accessorKey: "current_period_end",
      header: "Renews",
      cell: ({ row }) => dateCell(row.original.current_period_end),
    },
    {
      accessorKey: "cancel_at_period_end",
      header: "Cancels",
      cell: ({ row }) => (row.original.cancel_at_period_end ? "Yes" : "No"),
    },
  ];
  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by user id…"
      emptyTitle="No subscriptions"
    />
  );
}

// --- generation jobs -------------------------------------------------------

export function JobsGrid() {
  const query = useAdminJobs();
  const columns: ColumnDef<GenerationJob, unknown>[] = [
    {
      accessorKey: "prompt",
      header: "Prompt",
      cell: ({ row }) => (
        <span className="block max-w-[36ch] truncate font-medium">
          {row.original.prompt}
        </span>
      ),
    },
    { accessorKey: "user_id", header: "User", cell: ({ row }) => mono(row.original.user_id) },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    { accessorKey: "model", header: "Model", cell: ({ row }) => mono(row.original.model) },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => dateCell(row.original.created_at),
    },
  ];
  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by prompt / status…"
      emptyTitle="No generation jobs"
    />
  );
}

// --- generated files -------------------------------------------------------

export function FilesGrid() {
  const query = useAdminFiles();
  const columns: ColumnDef<AdminFile, unknown>[] = [
    { accessorKey: "b2_key", header: "B2 Key", cell: ({ row }) => mono(row.original.b2_key) },
    { accessorKey: "user_id", header: "User", cell: ({ row }) => mono(row.original.user_id) },
    {
      accessorKey: "media_type",
      header: "Type",
      cell: ({ row }) => row.original.media_type || "—",
    },
    {
      accessorKey: "size_bytes",
      header: "Size",
      cell: ({ row }) => humanizeBytes(row.original.size_bytes ?? 0),
    },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => dateCell(row.original.created_at),
    },
  ];
  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by key…"
      emptyTitle="No files"
    />
  );
}

// --- provider runs ---------------------------------------------------------

export function ProviderRunsGrid() {
  const query = useAdminProviderRuns();
  const columns: ColumnDef<AdminProviderRun, unknown>[] = [
    { accessorKey: "provider", header: "Provider" },
    { accessorKey: "model", header: "Model", cell: ({ row }) => mono(row.original.model) },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    { accessorKey: "assets_count", header: "Assets" },
    { accessorKey: "run_id", header: "Run", cell: ({ row }) => mono(row.original.run_id) },
    {
      accessorKey: "created_at",
      header: "Created",
      cell: ({ row }) => dateCell(row.original.created_at),
    },
  ];
  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by provider / status…"
      emptyTitle="No provider runs"
    />
  );
}

// --- audit log -------------------------------------------------------------

export function AuditGrid() {
  const query = useAdminAudit();
  const columns: ColumnDef<AdminAuditEvent, unknown>[] = [
    {
      accessorKey: "created_at",
      header: "When",
      cell: ({ row }) => dateCell(row.original.created_at),
    },
    { accessorKey: "actor_email", header: "Actor", cell: ({ row }) => row.original.actor_email || "—" },
    { accessorKey: "action", header: "Action" },
    { accessorKey: "resource", header: "Resource" },
    { accessorKey: "target_id", header: "Target", cell: ({ row }) => mono(row.original.target_id) },
    {
      id: "detail",
      header: "Detail",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {JSON.stringify(row.original.detail)}
        </span>
      ),
    },
  ];
  return (
    <AdminGrid
      query={query}
      columns={columns}
      filterPlaceholder="Filter by action / actor…"
      emptyTitle="No admin actions recorded yet"
    />
  );
}
