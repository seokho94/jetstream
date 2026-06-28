"use client";

import { useEffect, useState } from "react";
import { hueFor, type RankedRow } from "@jetstream/shared";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";
import { Sparkline } from "@/components/charts/Sparkline";

const WATCH = "jetstream.watch"; // followed current ids (CANON R13)
const SEEN = "jetstream.watch.seen"; // currentId -> state at last visit
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function FollowingPage() {
  const [rows, setRows] = useState<RankedRow[] | null>(null);
  const [changed, setChanged] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      let watch: string[] = [];
      try {
        watch = JSON.parse(localStorage.getItem(WATCH) || "[]");
      } catch {
        /* ignore */
      }
      if (!watch.length) {
        setRows([]);
        return;
      }
      let ranked: RankedRow[] = [];
      try {
        const res = await fetch(`${BASE}/v1/board`);
        if (res.ok) ranked = ((await res.json()).ranked as RankedRow[]) ?? [];
      } catch {
        /* ignore */
      }
      const mine = ranked.filter((r) => watch.includes(r.currentId));
      // highlight currents whose state changed since the last visit (anti-bubble: surface change, not hide)
      let seen: Record<string, string> = {};
      try {
        seen = JSON.parse(localStorage.getItem(SEEN) || "{}");
      } catch {
        /* ignore */
      }
      const ch: Record<string, string> = {};
      for (const r of mine) if (seen[r.currentId] && seen[r.currentId] !== r.state) ch[r.currentId] = seen[r.currentId];
      setChanged(ch);
      const next: Record<string, string> = {};
      for (const r of mine) next[r.currentId] = r.state;
      try {
        localStorage.setItem(SEEN, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      setRows(mine);
    })();
  }, []);

  return (
    <div className="following">
      <header className="appbar">
        <div className="brand">
          <span className="dot" />
          <span>Following</span>
        </div>
        <span className="asof">내가 주목한 흐름</span>
      </header>

      <p className="micro">
        전세계 board는 <a href="/board">Currents</a> 탭에 항상 그대로 — 여기는 보조 렌즈입니다.
      </p>

      {rows === null && <p className="micro">불러오는 중…</p>}

      {rows?.length === 0 && (
        <div className="empty-follow">
          <b>아직 주목한 흐름이 없어요.</b>
          <p>흐름 상세에서 알림 토글을 켜면 여기에 모입니다.</p>
          <a className="go" href="/board">
            board로 가기 →
          </a>
        </div>
      )}

      {rows && rows.length > 0 && (
        <ol className="ranked">
          {rows.map((r) => (
            <li key={r.currentId} style={vars({ "--c": hueFor(r.colorKey) })}>
              <a className="rrow" href={`/current/${r.currentId}`}>
                <span className="tick" />
                <span className="nm">{r.name}</span>
                <Sparkline data={r.sparkline} color={hueFor(r.colorKey)} />
                <MomentumBadge state={r.state} />
                {changed[r.currentId] && <span className="change">변화</span>}
                <span className="chev">›</span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
