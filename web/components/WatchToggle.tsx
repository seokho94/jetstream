"use client";

import { useEffect, useState } from "react";

const KEY = "jetstream.watch"; // Phase 0: localStorage (CANON R13)

/** "Alert me when this moves" — a real toggle (localStorage). */
export function WatchToggle({ currentId }: { currentId: string }) {
  const [on, setOn] = useState(false);

  useEffect(() => {
    try {
      const set: string[] = JSON.parse(localStorage.getItem(KEY) || "[]");
      setOn(set.includes(currentId));
    } catch {
      /* ignore */
    }
  }, [currentId]);

  function toggle() {
    try {
      const set: string[] = JSON.parse(localStorage.getItem(KEY) || "[]");
      const next = set.includes(currentId) ? set.filter((x) => x !== currentId) : [...set, currentId];
      localStorage.setItem(KEY, JSON.stringify(next));
      setOn(next.includes(currentId));
    } catch {
      /* ignore */
    }
  }

  return (
    <button className={`watch-toggle${on ? " on" : ""}`} onClick={toggle} aria-pressed={on} type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 5a2 2 0 1 1 4 0a7 7 0 0 1 4 6v3a4 4 0 0 0 2 3h-16a4 4 0 0 0 2 -3v-3a7 7 0 0 1 4 -6" />
        <path d="M9 17v1a3 3 0 0 0 6 0v-1" />
      </svg>
      <span>{on ? "알림 켜짐 — 이 흐름이 움직이면 알려드려요" : "이 흐름이 움직일 때 알림 받기"}</span>
    </button>
  );
}
