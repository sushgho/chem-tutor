import "./globals.css";
import type { ReactNode } from "react";

export const metadata = { title: "Chemistry Tutor", description: "AI chemistry teacher for Classes XI-XII" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
