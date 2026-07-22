"use client";

import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ApiError,
  createCheckout,
  createPortal,
  deleteFile,
  generateImage,
  getAdminAudit,
  getAdminFiles,
  getAdminJobs,
  getAdminOverview,
  getAdminProviderRuns,
  getAdminSubscriptions,
  getAdminUsers,
  getEntitlements,
  getFiles,
  getFileStats,
  getGenerationJobs,
  getHealth,
  getMe,
  getPlans,
  getPreviewUrl,
  getProPreview,
  getSubscription,
  getUploadActivity,
  setUserRole,
  type Me,
} from "@/lib/api-client";
import type {
  AdminAuditEvent,
  AdminFile,
  AdminOverview,
  AdminProviderRun,
  AdminUser,
  Entitlements,
  FileMetadata,
  GenerationJob,
  Plan,
  Role,
  Subscription,
} from "@ai-saas-starter-kit/shared";

// Single source of truth for query keys. Keep these tightly scoped so that
// invalidating "files" doesn't blow away unrelated caches, and so an IDE
// "find usages" of `qk.files` reveals every consumer.
export const qk = {
  all: ["b2"] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  stats: () => [...qk.all, "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  health: () => [...qk.all, "health"] as const,
  me: () => [...qk.all, "me"] as const,
  plans: () => [...qk.all, "plans"] as const,
  subscription: () => [...qk.all, "subscription"] as const,
  entitlements: () => [...qk.all, "entitlements"] as const,
  proPreview: () => [...qk.all, "proPreview"] as const,
  generationJobs: () => [...qk.all, "generationJobs"] as const,
  admin: {
    overview: () => [...qk.all, "admin", "overview"] as const,
    users: () => [...qk.all, "admin", "users"] as const,
    subscriptions: () => [...qk.all, "admin", "subscriptions"] as const,
    jobs: () => [...qk.all, "admin", "jobs"] as const,
    files: () => [...qk.all, "admin", "files"] as const,
    providerRuns: () => [...qk.all, "admin", "providerRuns"] as const,
    audit: () => [...qk.all, "admin", "audit"] as const,
  },
};

export type Health = Awaited<ReturnType<typeof getHealth>>;

// Invalidate exactly the caches a file mutation (upload/delete/generate) can
// change — the file lists, stats, and upload-activity — and nothing else.
// Previously mutations invalidated `qk.all` (["b2"]), which force-refetched
// health, entitlements, plans, and every rendered preview URL on each mutation.
// `qk.uploadActivity` is nested under `qk.stats`, so invalidating stats covers it.
export function invalidateFileData(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: [...qk.all, "files"] });
  qc.invalidateQueries({ queryKey: qk.stats() });
}

export function useFiles(prefix = "", limit = 100, enabled = true) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
    enabled,
  });
}

export function useFileStats() {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

// Health poll for the top-of-app B2 banner. `retry: false` and letting a
// failed fetch leave `data` undefined keeps a down API silent (the
// per-component ErrorState covers that); the banner only reacts to an up API
// reporting b2_connected: false. Polls every 60s and on window focus.
export function useHealth() {
  return useQuery<Health>({
    queryKey: qk.health(),
    queryFn: getHealth,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  });
}

// The authenticated identity as seen by the backend. Not retried on auth
// failure (the query client already skips retries on 4xx), so a signed-out or
// unreachable API surfaces as isError rather than spinning.
export function useMe(enabled = true) {
  return useQuery<Me, ApiError>({
    queryKey: qk.me(),
    queryFn: getMe,
    staleTime: 60_000,
    enabled,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    // Refetch only the file lists + stats the delete affects — not health,
    // entitlements, plans, or every open preview URL.
    onSuccess: () => invalidateFileData(qc),
  });
}

// --- Billing ---------------------------------------------------------------

export function usePlans() {
  return useQuery<Plan[], ApiError>({
    queryKey: qk.plans(),
    queryFn: getPlans,
    staleTime: 5 * 60_000, // catalog rarely changes
  });
}

export function useSubscription(enabled = true) {
  return useQuery<Subscription, ApiError>({
    queryKey: qk.subscription(),
    queryFn: getSubscription,
    enabled,
  });
}

export function useEntitlements(enabled = true) {
  return useQuery<Entitlements, ApiError>({
    queryKey: qk.entitlements(),
    queryFn: getEntitlements,
    enabled,
  });
}

// Pro-gated probe: succeeds on Pro/Team, errors with status 402 on Free. The
// Billing page reads `isError && error.status === 402` to show the locked state.
export function useProPreview(enabled = true) {
  return useQuery({
    queryKey: qk.proPreview(),
    queryFn: getProPreview,
    enabled,
    retry: false,
  });
}

// Redirects the browser to Stripe on success. Kept a mutation (not a query) so
// it only fires on an explicit click.
export function useCheckout() {
  return useMutation<{ url: string }, ApiError, string>({
    mutationFn: (planId: string) => createCheckout(planId),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
  });
}

export function usePortal() {
  return useMutation<{ url: string }, ApiError, void>({
    mutationFn: () => createPortal(),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
  });
}

// --- Generation ------------------------------------------------------------

// A user's generation jobs, newest first (each with its generated assets).
export function useGenerationJobs(enabled = true) {
  return useQuery<GenerationJob[], ApiError>({
    queryKey: qk.generationJobs(),
    queryFn: getGenerationJobs,
    enabled,
  });
}

// Run one text-to-image generation. On success we invalidate the job list AND
// the file caches — the new asset also lands in the B2-backed file manager.
export function useGenerate() {
  const qc = useQueryClient();
  return useMutation<GenerationJob, ApiError, { prompt: string; seed?: number | null }>({
    mutationFn: ({ prompt, seed }) => generateImage(prompt, seed),
    onSuccess: () => {
      // A generated asset lands in the file manager too, so refresh the job list
      // AND the file caches — but not unrelated queries.
      qc.invalidateQueries({ queryKey: qk.generationJobs() });
      invalidateFileData(qc);
    },
  });
}

// --- Admin -----------------------------------------------------------------
// All admin queries are gated to admins server-side (401/403). The console only
// mounts these hooks after `admin/page.tsx` confirms the caller is an admin (it
// renders null otherwise), so in practice a non-admin never fires them. The
// optional `enabled` flag is kept for callers that want to defer a fetch;
// retry:false stops a 403 from spinning.

export function useAdminOverview(enabled = true) {
  return useQuery<AdminOverview, ApiError>({
    queryKey: qk.admin.overview(),
    queryFn: getAdminOverview,
    enabled,
    retry: false,
  });
}

export function useAdminUsers(enabled = true) {
  return useQuery<AdminUser[], ApiError>({
    queryKey: qk.admin.users(),
    queryFn: getAdminUsers,
    enabled,
    retry: false,
  });
}

export function useAdminSubscriptions(enabled = true) {
  return useQuery<Subscription[], ApiError>({
    queryKey: qk.admin.subscriptions(),
    queryFn: getAdminSubscriptions,
    enabled,
    retry: false,
  });
}

export function useAdminJobs(enabled = true) {
  return useQuery<GenerationJob[], ApiError>({
    queryKey: qk.admin.jobs(),
    queryFn: getAdminJobs,
    enabled,
    retry: false,
  });
}

export function useAdminFiles(enabled = true) {
  return useQuery<AdminFile[], ApiError>({
    queryKey: qk.admin.files(),
    queryFn: getAdminFiles,
    enabled,
    retry: false,
  });
}

export function useAdminProviderRuns(enabled = true) {
  return useQuery<AdminProviderRun[], ApiError>({
    queryKey: qk.admin.providerRuns(),
    queryFn: getAdminProviderRuns,
    enabled,
    retry: false,
  });
}

export function useAdminAudit(enabled = true) {
  return useQuery<AdminAuditEvent[], ApiError>({
    queryKey: qk.admin.audit(),
    queryFn: getAdminAudit,
    enabled,
    retry: false,
  });
}

// Change a user's role. Invalidates the users list, the audit log, and the
// overview counts (admin count may shift).
export function useSetUserRole() {
  const qc = useQueryClient();
  return useMutation<AdminUser, ApiError, { userId: string; role: Role }>({
    mutationFn: ({ userId, role }) => setUserRole(userId, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.admin.users() });
      qc.invalidateQueries({ queryKey: qk.admin.audit() });
      qc.invalidateQueries({ queryKey: qk.admin.overview() });
    },
  });
}
