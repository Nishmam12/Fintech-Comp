import type { Metadata, Viewport } from "next";
import { Archivo, Caveat } from "next/font/google";
import "./globals.css";
import "./ui.css";

// Archivo's width axis carries the display look: wdth 125 for figures and headings, 100 for text (see .fig in ui.css).
const archivo = Archivo({ variable: "--nf-archivo", subsets: ["latin"], axes: ["wdth"] });

// The handwritten look of the first-visit guide only (components/Tour.tsx).
const hand = Caveat({ variable: "--nf-hand", subsets: ["latin"], weight: ["600", "700"] });

export const metadata: Metadata = {
  title: "Budget Kernel",
  description: "Models propose. The kernel decides.",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export const viewport: Viewport = { themeColor: "#f1f2ee" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${archivo.variable} ${hand.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
