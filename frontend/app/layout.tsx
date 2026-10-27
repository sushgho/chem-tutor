import "./globals.css";
import type { ReactNode } from "react";
import PwaServiceWorker from "@/components/PwaServiceWorker";

export const metadata = {
  title: "Chemistry Tutor",
  description: "AI chemistry teacher for Classes XI-XII",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default" as const,
    title: "Chemistry Tutor",
  },
  icons: {
    icon: [{ url: "/icons/chemistry-tutor.svg", type: "image/svg+xml", sizes: "any" }],
    apple: "/icons/chemistry-tutor.svg",
  },
};

export const viewport = {
  themeColor: "#3b6ea5",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PwaServiceWorker />
        {children}
      </body>
    </html>
  );
}
