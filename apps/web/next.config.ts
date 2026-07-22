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
// Baseline security response headers applied to every route. Deliberately no
// Content-Security-Policy: a hardcoded CSP needs env-specific connect-src
// (Supabase + API origins) and would break the app when deployed elsewhere —
// clickjacking is already covered by X-Frame-Options: DENY. HSTS uses a 2-year
// max-age with includeSubDomains; it only takes effect over HTTPS, so it is a
// no-op on plain-HTTP localhost but pins production to HTTPS once served.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains",
  },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

const nextConfig: NextConfig = {
  transpilePackages: ["@ai-saas-starter-kit/shared"],
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
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
