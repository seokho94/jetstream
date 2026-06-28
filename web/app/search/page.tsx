"use client";

import { useState } from "react";
import { hueFor, type SearchHit } from "@jetstream/shared";
import { searchHits } from "@/lib/api";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    const r = await searchHits(q);
    setHits(r);
    setLoading(false);
    setDone(true);
  }

  const currents = hits.filter((h) => h.type === "current");
  const events = hits.filter((h) => h.type === "event");

  return (
    <div className="searchpage">
      <header className="appbar">
        <div className="brand">
          <span className="dot" />
          <span>Search</span>
        </div>
        <span className="asof">흐름 · 사건</span>
      </header>

      <form className="searchbar" onSubmit={run}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="흐름·사건 검색 (예: 이란, 기후, 트럼프)"
          aria-label="검색어"
          autoFocus
        />
        <button type="submit">검색</button>
      </form>

      {loading && <p className="micro">검색 중…</p>}
      {done && !loading && hits.length === 0 && <p className="empty">결과가 없습니다.</p>}

      {currents.length > 0 && (
        <>
          <p className="kicker" style={{ padding: "6px 18px 0" }}>
            흐름
          </p>
          <ul className="hitlist">
            {currents.map((h) => (
              <li key={h.id} style={vars({ "--c": hueFor(h.colorKey) })}>
                <a className="hit" href={`/current/${h.currentId}`}>
                  <span className="tick" />
                  <span className="hit-title">{h.title}</span>
                  {h.state && <MomentumBadge state={h.state} />}
                  <span className="chev">›</span>
                </a>
                {h.snippet && <p className="hit-snip">{h.snippet}</p>}
              </li>
            ))}
          </ul>
        </>
      )}

      {events.length > 0 && (
        <>
          <p className="kicker" style={{ padding: "6px 18px 0" }}>
            사건
          </p>
          <ul className="hitlist">
            {events.map((h) => (
              <li key={h.id} style={vars({ "--c": hueFor(h.colorKey) })}>
                <a className="hit" href={`/current/${h.currentId}`}>
                  <span className="hit-date">{h.date}</span>
                  <span className="hit-title ev">{h.title}</span>
                  <span className="chev">›</span>
                </a>
                <p className="hit-snip">
                  {h.snippet}
                  {h.url && (
                    <>
                      {" · "}
                      <a href={h.url} target="_blank" rel="noreferrer">
                        출처 ↗
                      </a>
                    </>
                  )}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
