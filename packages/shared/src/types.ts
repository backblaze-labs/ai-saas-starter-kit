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

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
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
