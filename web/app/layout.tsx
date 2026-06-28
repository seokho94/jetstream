import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Meridian — the world, zoomed out",
  description: "The 10–15 macro currents beneath global news, and which way they're moving.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="app">
          {children}
          <nav className="tabbar">
            <a href="/board" className="active">Currents</a>
            <a href="/board">Following</a>
            <a href="/digest/12">Digest</a>
            <a href="/board">Search</a>
          </nav>
        </div>
      </body>
    </html>
  );
}
