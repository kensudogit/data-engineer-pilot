import type { Metadata } from "next";
import Nav from "@/components/Nav";
import { UsageGuidePanel } from "@/components/UsageGuidePanel";
import "./globals.css";

export const metadata: Metadata = {
  title: "Data Engineer Pilot",
  description: "BigQuery ML想定の5機能（売上予測・解約予測・顧客分類・異常検知・需要予測）パイロット",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Nav />
        <main className="container">{children}</main>
        <UsageGuidePanel />
      </body>
    </html>
  );
}
