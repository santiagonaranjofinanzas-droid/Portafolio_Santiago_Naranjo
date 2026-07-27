import type { NextConfig } from "next";

const rawBackendApiBase = (process.env.BACKEND_API_BASE_URL  "https://black-knight-backend.onrender.com/api/v1").trim();
const backendApiBase = /^https?:\/\//i.test(rawBackendApiBase)
  ? rawBackendApiBase.replace(/\/+$/, "")
  : "https://black-knight-backend.onrender.com/api/v1";

const nextConfig: NextConfig = {
  // Allow local origins for Next.js dev HMR when server is bound to 0.0.0.0
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
  ],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendApiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
