import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Public_Sans } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({
  variable: "--nf-display",
  subsets: ["latin"],
});

const body = Public_Sans({
  variable: "--nf-body",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Budget Kernel",
  description: "Models propose. The kernel decides.",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export const viewport: Viewport = { themeColor: "#0e1a2b" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
