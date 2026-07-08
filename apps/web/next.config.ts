import type { NextConfig } from "next";

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
