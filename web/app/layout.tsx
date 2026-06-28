import type { Metadata } from "next";
import "./globals.css";
import { TabBar } from "@/components/TabBar";

export const metadata: Metadata = {
  title: "Jetstream — the world, zoomed out",
  description: "The 10–15 macro currents beneath global news, and which way they're moving.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="app">
          {children}
          <TabBar />
        </div>
      </body>
    </html>
  );
}
