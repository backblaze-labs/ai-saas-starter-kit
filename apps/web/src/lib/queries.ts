"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createCheckout,
  createPortal,
  deleteFile,
  getEntitlements,
  getFiles,
  getFileStats,
  getMe,
  getPlans,
  getPreviewUrl,
  getProPreview,
  getSubscription,
  getUploadActivity,
  type Me,
} from "@/lib/api-client";
import type {
  Entitlements,
  FileMetadata,
  Plan,
  Subscription,
} from "@ai-media-saas-starter/shared";

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
  me: () => [...qk.all, "me"] as const,
  plans: () => [...qk.all, "plans"] as const,
  subscription: () => [...qk.all, "subscription"] as const,
  entitlements: () => [...qk.all, "entitlements"] as const,
  proPreview: () => [...qk.all, "proPreview"] as const,
};

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
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
    // After delete, blow away every cached file list + stats. Cheap and
    // correct — the dashboard re-fetches lazily as components remount.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
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
