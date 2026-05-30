import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fabric Admin",
  description: "Manage fabric-server skills and graph content",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Reading x-nonce here causes Next.js to inject the nonce into its own
  // inline bootstrap scripts, enabling nonce-based CSP without unsafe-inline.
  await headers();

  return (
    <html lang="en" data-theme="dark">
      <body className="bg-base-100 text-base-content">{children}</body>
    </html>
  );
}
