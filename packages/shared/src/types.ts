export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

/** Sent to POST /upload/presign — the intent to upload, no bytes. */
export interface PrepareUploadRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
}

/** A short-lived presigned PUT the browser uses to upload straight to B2. */
export interface PresignedUpload {
  upload_url: string;
  key: string;
  method: string;
  /** Headers the browser must replay on the PUT (currently Content-Type). */
  headers: Record<string, string>;
}

/** Sent to POST /upload/complete once the browser's PUT to B2 succeeds. */
export interface CompleteUploadRequest {
  key: string;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Billing ---------------------------------------------------------------

export type PlanTier = "free" | "pro" | "team";

export interface Plan {
  id: PlanTier;
  name: string;
  rank: number;
  price_cents: number;
  currency: string;
  interval: string;
  features: string[];
  is_public: boolean;
}

export interface Subscription {
  user_id: string;
  plan_id: PlanTier;
  status: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  /** Stripe is in test mode (sk_test_ key) — gates test-only UI hints. */
  test_mode: boolean;
}

export interface Entitlements {
  tier: PlanTier;
  rank: number;
  active: boolean;
  can_generate: boolean;
}

// --- Generation ------------------------------------------------------------

export type GenerationStatus = "running" | "succeeded" | "failed";

export interface GenerateRequest {
  prompt: string;
  seed?: number | null;
}

export interface GeneratedAsset {
  key: string;
  url: string | null;
  sha256: string | null;
  media_type: string;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
}

export interface GenerationJob {
  id: string;
  user_id: string;
  prompt: string;
  provider: string;
  model: string;
  status: GenerationStatus;
  error: string | null;
  seed: number | null;
  run_id: string | null;
  manifest_uri: string | null;
  canonical_hash: string | null;
  cost_usd: number | null;
  assets: GeneratedAsset[];
  created_at: string | null;
}

// --- Admin -----------------------------------------------------------------

export type Role = "user" | "admin";

export interface AdminOverview {
  users: number;
  admins: number;
  active_subscriptions: number;
  generation_jobs: number;
  failed_jobs: number;
  files: number;
  storage_bytes: number;
  provider_runs: number;
  webhook_events: number;
}

export interface AdminUser {
  id: string;
  email: string | null;
  full_name: string | null;
  role: string;
  created_at: string | null;
}

export interface AdminFile {
  id: string;
  user_id: string;
  job_id: string | null;
  b2_key: string;
  url: string | null;
  media_type: string | null;
  size_bytes: number | null;
  created_at: string | null;
}

export interface AdminProviderRun {
  id: string;
  job_id: string;
  provider: string;
  model: string;
  run_id: string | null;
  status: string;
  cost_usd: number | null;
  assets_count: number;
  created_at: string | null;
}

export interface AdminAuditEvent {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  resource: string;
  target_id: string | null;
  detail: Record<string, unknown>;
  created_at: string | null;
}
