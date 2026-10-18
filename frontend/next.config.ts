import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Always inline the demo keys, empty when unset, so a build without them folds the demo buttons away (BK-511).
  // Dev server only: `next build` runs with NODE_ENV=production, so a production bundle never carries a key even
  // when frontend/.env.local is present (review finding B1).
  env: { NEXT_PUBLIC_DEMO_KEYS: process.env.NODE_ENV === "production" ? "" : (process.env.NEXT_PUBLIC_DEMO_KEYS ?? "") },
  // The dev "N" badge sits on the phone tab bar and in the demo video; hide it.
  devIndicators: false,
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
