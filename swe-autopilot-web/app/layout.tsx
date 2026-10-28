import type { Metadata } from "next";
import { AuthSessionProvider } from "@/components/auth-session";
import "./globals.css";

export const metadata: Metadata = {
  title: "SWE Autopilot — Autonomous software engineering",
  description:
    "A traceable, evidence-driven software engineering control plane for requirements, code, testing, security and release.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AuthSessionProvider>{children}</AuthSessionProvider>
      </body>
    </html>
  );
}
