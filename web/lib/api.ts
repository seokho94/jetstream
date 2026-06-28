// Phase 0 → 1 data access. The client reads only published view objects (spec §6),
// served by the FastAPI layer at NEXT_PUBLIC_API_BASE. Fetches use ISR
// (revalidate = CANON ISR_REVALIDATE 180s). If the API is unreachable, we fall
// back to local seed so dev/build still work without the backend running.
import {
  buildBoard,
  buildCurrentView,
  buildDigest,
  type BoardView,
  type CurrentView,
  type Digest,
  type SearchHit,
} from "@jetstream/shared";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const REVALIDATE = 180; // seconds (CANON §7 ISR_REVALIDATE)

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { next: { revalidate: REVALIDATE } });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return (await res.json()) as T;
  } catch {
    return null; // API down → caller falls back to seed
  }
}

export async function getBoard(): Promise<BoardView> {
  return (await fetchJson<BoardView>("/v1/board")) ?? buildBoard();
}

export async function getCurrent(id: string): Promise<CurrentView | null> {
  // Distinguish a genuine 404 (→ notFound) from an API outage (→ seed fallback).
  try {
    const res = await fetch(`${BASE}/v1/currents/${id}`, { next: { revalidate: REVALIDATE } });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`currents/${id} → ${res.status}`);
    return (await res.json()) as CurrentView;
  } catch {
    return buildCurrentView(id); // API down → seed (null if seed lacks it)
  }
}

export async function getDigest(issue: number): Promise<Digest> {
  return (await fetchJson<Digest>(`/v1/digests/${issue}`)) ?? buildDigest(issue);
}

// Client-callable (no ISR cache) — search is interactive and per-query.
export async function searchHits(q: string): Promise<SearchHit[]> {
  if (!q.trim()) return [];
  try {
    const res = await fetch(`${BASE}/v1/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) return [];
    const data = (await res.json()) as { results: SearchHit[] };
    return data.results ?? [];
  } catch {
    return [];
  }
}
