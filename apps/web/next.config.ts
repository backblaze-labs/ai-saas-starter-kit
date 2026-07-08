import { join } from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// This is a monorepo: env lives in the repo-root .env (shared with the FastAPI
// backend), not in apps/web. Load it here so NEXT_PUBLIC_* vars (Supabase URL +
// anon key, API URL) are inlined at build time and available at runtime. Does
// not override anything already set in the environment (e.g. dev.sh exports).
loadEnvConfig(join(process.cwd(), "..", ".."), process.env.NODE_ENV !== "production");

// Allow `next/image` to optimize remote previews coming from Backblaze B2.
// Presigned download URLs use the bucket-specific S3 hostname pattern:
//   <bucket>.s3.<region>.backblazeb2.com    (path-style and virtual-host)
//   s3.<region>.backblazeb2.com             (path-style)
// One wildcard covers every region + bucket, so this config drops in
// without per-deployment tweaks.
const nextConfig: NextConfig = {
  transpilePackages: ["@ai-media-saas-starter/shared"],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.backblazeb2.com",
      },
    ],
  },
};

export default nextConfig;
