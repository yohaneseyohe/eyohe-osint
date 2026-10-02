import type { NextConfig } from "next";

// The browser talks to same-origin /api/* so the HttpOnly session cookie and
// the readable CSRF cookie just work; Next proxies to the FastAPI backend.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Dev-only: lets the HMR client connect when the app is opened via 127.0.0.1 instead of localhost.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    // `fallback` so the few route handlers under src/app/api (e.g. the SSE
    // passthrough) take precedence; everything else is proxied to FastAPI.
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }],
    };
  },
};

export default nextConfig;
