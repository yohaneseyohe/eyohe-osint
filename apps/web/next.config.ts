import type { NextConfig } from "next";

// The browser talks to same-origin /api/* so the HttpOnly session cookie and
// the readable CSRF cookie just work; Next proxies to the FastAPI backend.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
};

export default nextConfig;
