import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" output is for self-hosted Docker only — Vercel manages its own server.
  // Set NEXT_OUTPUT=standalone at Docker build time to enable it for containerised deploys.
  ...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" } : {}),
};

export default nextConfig;
