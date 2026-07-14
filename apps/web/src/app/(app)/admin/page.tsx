"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";
import { AdminConsole } from "@/components/admin/admin-console";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Admin console route. The (app) group middleware already requires a session;
 * this adds a role gate. The gate is UX only — every /admin API endpoint is
 * independently admin-gated server-side (401/403), so the data is protected
 * regardless of what renders here.
 *
 * `profile` is null until the profile query resolves. We wait for it before
 * deciding, so an admin never gets bounced during the initial load.
 */
export default function AdminPage() {
  const { user, profile, isAdmin } = useAuth();
  const router = useRouter();

  const resolved = Boolean(user && profile);

  useEffect(() => {
    if (resolved && !isAdmin) router.replace("/");
  }, [resolved, isAdmin, router]);

  if (!resolved) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!isAdmin) return null; // redirecting

  return <AdminConsole />;
}
