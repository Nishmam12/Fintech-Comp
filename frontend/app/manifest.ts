import type { MetadataRoute } from "next";

// PWA manifest (BK-321). Installable shell only: no service worker, so no authenticated API response is ever cached offline.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Budget Kernel",
    short_name: "Budget Kernel",
    description: "Models propose. The kernel decides.",
    start_url: "/",
    display: "standalone",
    background_color: "#0f172a",
    theme_color: "#0f172a",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
