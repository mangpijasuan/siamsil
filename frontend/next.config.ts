import type { NextConfig } from "next";
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

// Rewrites are resolved at build time, so SIAMSIL_API_URL must be set in the build environment.
const backendUrl =
  process.env.SIAMSIL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8001";

initOpenNextCloudflareForDev();

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  devIndicators: false,
  turbopack: {
    root: import.meta.dirname,
  },
  async redirects() {
    return [
      // Old paths → SEO-friendly URLs
      { source: "/dictionary", destination: "/zomidictionary", permanent: true },
      { source: "/dictionary/:path*", destination: "/zomidictionary/:path*", permanent: true },
      { source: "/translate", destination: "/zomitranslate", permanent: true },
      { source: "/translate/:path*", destination: "/zomitranslate/:path*", permanent: true },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
