import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Always inline the demo keys, empty when unset, so a build without them folds the demo buttons away (BK-511).
  env: { NEXT_PUBLIC_DEMO_KEYS: process.env.NEXT_PUBLIC_DEMO_KEYS ?? "" },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
