import type {
  AdminAuditEvent,
  AdminFile,
  AdminOverview,
  AdminProviderRun,
  AdminUser,
  DailyUploadCount,
  Entitlements,
  FileMetadata,
  FileUploadResponse,
  GenerationJob,
  Plan,
  Role,
  Subscription,
  UploadStats,
} from "@ai-saas-starter-kit/shared";
import { createClient } from "./supabase/client";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Attach the current Supabase access token as a bearer header when a session
 * exists. Returns an empty object on the server or when signed out, so
 * unauthenticated/public endpoints keep working unchanged.
 */
async function authHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") return {};
  try {
    const {
      data: { session },
    } = await createClient().auth.getSession();
    return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
  } catch {
    return {};
  }
}

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

/**
 * Build the right status-0 ApiError for a thrown fetch().
 *
 * fetch() rejects with a TypeError for genuinely-offline/DNS failures AND for
 * responses the browser refused to expose — most notably a cross-origin 500
 * that shipped without `Access-Control-Allow-Origin`. We can't tell those apart
 * from the error object, but `navigator.onLine === false` reliably means the
 * device has no connectivity. Anything else reached the network, so the most
 * likely cause is the server erroring with a CORS-blocked response. Either way
 * the customer just needs to retry, so keep the copy generic — developers see
 * the real failure in the browser network tab / API logs.
 */
function networkError(): ApiError {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return new ApiError("You appear to be offline — check your connection", 0);
  }
  return new ApiError("Couldn't reach the server. Please try again.", 0);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = {
    ...(init?.headers as Record<string, string> | undefined),
    ...(await authHeaders()),
  };
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw networkError();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.detail || `API error: ${res.status}`,
      res.status,
    );
  }
  return res.json();
}

function isEndpointUnavailable(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    error.status === 404 &&
    (error.message === "Not Found" || error.message === "API error: 404")
  );
}

async function apiFetchWithLegacyFallback<T>(
  path: string,
  legacyPath: () => string,
  init?: RequestInit
): Promise<T> {
  try {
    return await apiFetch<T>(path, init);
  } catch (error) {
    if (isEndpointUnavailable(error)) {
      return apiFetch<T>(legacyPath(), init);
    }
    throw error;
  }
}

function fileKeyQuery(key: string): string {
  if (key.length === 0) {
    throw new ApiError("File key is required", 400);
  }
  return new URLSearchParams({ key }).toString();
}

function legacyFileKeyPath(
  key: string,
  options: { blockRouteCollisions?: boolean } = {}
): string {
  if (!isLegacyPathFallbackSafe(key, options)) {
    throw new ApiError("Current API version required for this file key", 404);
  }
  return encodeURIComponent(key);
}

function isLegacyPathFallbackSafe(
  key: string,
  { blockRouteCollisions = false }: { blockRouteCollisions?: boolean } = {}
): boolean {
  if (/(\.\.\/|\/\.\.|\\|%2e%2e|%00|\x00)/i.test(key)) return false;
  if (!blockRouteCollisions) return true;

  const lowerKey = key.toLowerCase();
  if (lowerKey === "stats" || lowerKey === "stats/activity") return false;
  if (lowerKey.endsWith("/download") || lowerKey.endsWith("/preview")) return false;
  return true;
}

export async function getHealth() {
  return apiFetch<{ status: string; b2_connected: boolean }>("/health");
}

export async function getFiles(prefix = "", limit = 100) {
  return apiFetch<FileMetadata[]>(
    `/files?prefix=${encodeURIComponent(prefix)}&limit=${limit}`
  );
}

export async function getFileStats() {
  return apiFetch<UploadStats>("/files/stats");
}

export async function getUploadActivity(days = 7) {
  return apiFetch<DailyUploadCount[]>(`/files/stats/activity?days=${days}`);
}

export async function getFile(key: string) {
  return apiFetchWithLegacyFallback<FileMetadata>(
    `/files-by-key/metadata?${fileKeyQuery(key)}`,
    () => `/files/${legacyFileKeyPath(key, { blockRouteCollisions: true })}`
  );
}

export async function getDownloadUrl(key: string) {
  return apiFetchWithLegacyFallback<{ url: string }>(
    `/files-by-key/download?${fileKeyQuery(key)}`,
    () => `/files/${legacyFileKeyPath(key)}/download`
  );
}

/** Preview-only presigned URL — does NOT increment the download counter. */
export async function getPreviewUrl(key: string) {
  return apiFetchWithLegacyFallback<{ url: string }>(
    `/files-by-key/preview?${fileKeyQuery(key)}`,
    () => `/files/${legacyFileKeyPath(key)}/preview`
  );
}

export async function deleteFile(key: string) {
  return apiFetchWithLegacyFallback<{ deleted: boolean; key: string }>(
    `/files-by-key?${fileKeyQuery(key)}`,
    () => `/files/${legacyFileKeyPath(key)}`,
    {
      method: "DELETE",
    }
  );
}

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<FileUploadResponse> {
  const headers = await authHeaders();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || `Upload failed: ${xhr.status}`, xhr.status));
        } catch {
          reject(new ApiError(`Upload failed: ${xhr.status}`, xhr.status));
        }
      }
    });

    xhr.addEventListener("error", () => reject(networkError()));
    xhr.addEventListener("abort", () =>
      reject(new ApiError("Upload aborted", 0)),
    );

    xhr.open("POST", `${API_BASE}/upload`);
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.send(formData);
  });
}

export type Me = { id: string; email: string | null; role: string };

/** The authenticated identity as validated by the FastAPI backend (GET /me). */
export async function getMe() {
  return apiFetch<Me>("/me");
}

// --- Billing ---------------------------------------------------------------

/** Public plan catalog (Free/Pro/Team). */
export async function getPlans() {
  return apiFetch<Plan[]>("/billing/plans");
}

/** The caller's current subscription (synthesised Free when never subscribed). */
export async function getSubscription() {
  return apiFetch<Subscription>("/billing/subscription");
}

/** The caller's derived entitlements (tier + feature flags). */
export async function getEntitlements() {
  return apiFetch<Entitlements>("/billing/entitlements");
}

/** Start a Stripe Checkout Session for a plan; returns the hosted checkout URL. */
export async function createCheckout(planId: string) {
  return apiFetch<{ url: string }>("/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId }),
  });
}

/** Open the Stripe Billing Portal; returns the hosted portal URL. */
export async function createPortal() {
  return apiFetch<{ url: string }>("/billing/portal", { method: "POST" });
}

/**
 * Pro-gated demo endpoint. Resolves when the caller is on Pro/Team, and throws
 * an ApiError with status 402 for Free — the Billing page uses that to render
 * the locked vs. unlocked state.
 */
export async function getProPreview() {
  return apiFetch<{ unlocked: boolean; message: string }>("/billing/pro/preview");
}

// --- Generation ------------------------------------------------------------

/**
 * Run one text-to-image generation. Pro-gated: throws ApiError 402 for Free,
 * 503 when NVIDIA isn't configured. On success the assets are already in B2.
 */
export async function generateImage(prompt: string, seed?: number | null) {
  return apiFetch<GenerationJob>("/generation/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, seed: seed ?? null }),
  });
}

/** The caller's generation jobs (newest first), each with its generated assets. */
export async function getGenerationJobs() {
  return apiFetch<GenerationJob[]>("/generation/jobs");
}

// --- Admin -----------------------------------------------------------------
// Every /admin endpoint is admin-gated server-side (401 signed-out, 403
// non-admin), so these throw an ApiError with that status for a non-admin.

/** Aggregate counts + storage across all users (admin console cards). */
export async function getAdminOverview() {
  return apiFetch<AdminOverview>("/admin/overview");
}

export async function getAdminUsers() {
  return apiFetch<AdminUser[]>("/admin/users");
}

export async function getAdminSubscriptions() {
  return apiFetch<Subscription[]>("/admin/subscriptions");
}

export async function getAdminJobs() {
  return apiFetch<GenerationJob[]>("/admin/jobs");
}

export async function getAdminFiles() {
  return apiFetch<AdminFile[]>("/admin/files");
}

export async function getAdminProviderRuns() {
  return apiFetch<AdminProviderRun[]>("/admin/provider-runs");
}

export async function getAdminAudit() {
  return apiFetch<AdminAuditEvent[]>("/admin/audit");
}

/** Change a user's role. Audited server-side; runs with the admin's own token. */
export async function setUserRole(userId: string, role: Role) {
  return apiFetch<AdminUser>(`/admin/users/${userId}/role`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}
