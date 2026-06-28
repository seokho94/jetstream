// Phase 0 seed — illustrative data (spec Appendix, June 2026). The three screens
// render from this so the app works without a DB or pipeline. Replace with the
// published store in Phase 1.
import type {
  BoardView,
  CurrentView,
  Digest,
  ArcPoint,
  MomentumState,
  StreamgraphSeries,
} from "./types";
import { currentHues } from "./tokens";

interface Meta {
  id: string;
  name: string;
  state: MomentumState;
  thisRank: number;
  lastRank: number;
  attention: number;
  blurb: string;
}

// Ranking = thisRank (spec Appendix reshuffle).
export const SEED_META: Meta[] = [
  { id: "ai-governance", name: "AI governance", state: "rising", thisRank: 1, lastRank: 3, attention: 0.94, blurb: "표준·감독 프레임워크가 빠르게 수렴하고 있습니다." },
  { id: "cost-of-living", name: "Cost of living", state: "peaking", thisRank: 2, lastRank: 1, attention: 0.86, blurb: "물가 압력이 고점에서 평탄화되는 신호입니다." },
  { id: "energy", name: "Energy", state: "rising", thisRank: 3, lastRank: 4, attention: 0.75, blurb: "전력망·재생에너지 투자가 꾸준히 누적되고 있습니다." },
  { id: "climate", name: "Climate", state: "rising", thisRank: 4, lastRank: 6, attention: 0.61, blurb: "극단 기후 사건이 정책 논의를 끌어올렸습니다." },
  { id: "middle-east", name: "Middle East", state: "cooling", thisRank: 5, lastRank: 2, attention: 0.52, blurb: "긴장이 고점을 지나 완화되는 국면입니다." },
  { id: "china", name: "China", state: "steady", thisRank: 6, lastRank: 5, attention: 0.42, blurb: "극적 사건 없이 꾸준한 기저 관심이 유지됩니다." },
];

const round2 = (x: number) => Math.round(x * 100) / 100;

function weekISO(i: number, total: number): string {
  // 6-month arc ending ~2026-06-28; weekly buckets.
  const start = new Date("2026-01-11T00:00:00Z");
  const d = new Date(start.getTime() + i * 7 * 86400000);
  return d.toISOString().slice(0, 10);
}

function sparkFor(seed: number, state: MomentumState): number[] {
  const out: number[] = [];
  for (let i = 0; i < 10; i++) {
    const base = (Math.sin(seed * 1.4 + i * 0.6) + 1) / 2;
    const drift =
      state === "rising" ? i * 0.05 : state === "cooling" ? -i * 0.04 : state === "peaking" ? 0.4 - Math.abs(i - 6) * 0.04 : 0;
    out.push(round2(Math.min(1, Math.max(0.05, base * 0.4 + 0.3 + drift))));
  }
  return out;
}

function arcFor(seed: number): ArcPoint[] {
  const N = 24;
  const pts: ArcPoint[] = [];
  for (let i = 0; i < N; i++) {
    const base = (Math.sin(seed * 1.1 + i * 0.5) + 1) / 2;
    const v = Math.min(1, Math.max(0.05, base * 0.5 + 0.18 + i * 0.013));
    pts.push({ t: weekISO(i, N), value: round2(v) });
  }
  const markerIdx = [4, 9, 14, 18, 23];
  markerIdx.forEach((p, k) => {
    pts[p]!.marker = k + 1;
    pts[p]!.eventId = `${seed}-e${k + 1}`;
  });
  return pts;
}

export function buildStreamgraph(): StreamgraphSeries[] {
  const weeks = 8;
  return SEED_META.slice(0, 6).map((m, mi) => ({
    currentId: m.id,
    colorKey: m.id,
    series: Array.from({ length: weeks }, (_, w) => {
      const base = (Math.sin(mi * 1.7 + w * 0.5) + 1) / 2;
      return { t: weekISO(16 + w, weeks), share: round2(0.08 + base * 0.18 + m.attention * 0.12) };
    }),
  }));
}

export function buildBoard(): BoardView {
  const asOf = "2026-06-28T09:00:00Z";
  const ranked = [...SEED_META]
    .sort((a, b) => a.thisRank - b.thisRank)
    .map((m) => ({
      currentId: m.id,
      name: m.name,
      colorKey: m.id,
      rank: m.thisRank,
      state: m.state,
      score: round2(m.attention),
      sparkline: sparkFor(m.thisRank + 1, m.state),
      attention: m.attention,
    }));
  return {
    id: 1,
    asOf,
    generatedAt: asOf,
    isCurrent: true,
    todaysRead: {
      paragraph:
        "세계는 AI 거버넌스로 시선이 쏠리는 한 주였습니다 — 규제 수렴이 가속하며 1위로 올라섰고, 생활비는 고점에서 평탄화, 중동은 긴장이 한 풀 꺾였습니다.",
      asOf,
    },
    streamgraph: buildStreamgraph(),
    ranked,
    digestTeaser: {
      issue: 12,
      weekOf: "2026-06-22",
      lede: "이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다.",
    },
    stats: { currentsTracked: 12, newThreads: 3, storiesScanned: 184320 },
    etag: "seed-board-1",
    lang: "en",
  };
}

export function buildCurrentView(id: string): CurrentView | null {
  const m = SEED_META.find((x) => x.id === id);
  if (!m) return null;
  const seed = m.thisRank + 2;
  const arc = arcFor(seed);
  const dates = arc.filter((p) => p.marker).map((p) => p.t);
  return {
    currentId: m.id,
    store: "published",
    version: 1,
    name: m.name,
    colorKey: m.id,
    rank: m.thisRank,
    state: m.state,
    arc,
    brief: {
      whatsHappening: `${m.name} — ${m.blurb}`,
      whyItMatters:
        "단발성 스파이크가 아니라 여러 주에 걸친 꾸준한 축적이라, 올해의 방향을 가늠하는 데 의미가 큽니다.",
      citations: [
        { text: m.blurb, outlet: "Reuters", url: "https://example.com/a", charStart: 0, charEnd: m.blurb.length },
      ],
    },
    timeline: dates.map((d, k) => ({
      node: k + 1,
      date: d,
      text: `${m.name} 전개 ${k + 1}: 주요 사건 요약 (시드 데이터).`,
      eventId: `${seed}-e${k + 1}`,
      isLatest: k === dates.length - 1,
      sources: [
        { text: "", outlet: k % 2 ? "AP" : "Reuters", url: "https://example.com/s", charStart: 0, charEnd: 12 },
      ],
    })),
    coverage: {
      axis: "region_block",
      minN: 5,
      buckets: [
        { label: "Europe", pct: 41, n: 38 },
        { label: "North America", pct: 33, n: 31 },
        { label: "Asia", pct: 26, n: 22 },
      ],
      hidden: [],
    },
    asOf: "2026-06-28T09:00:00Z",
    reviewedAt: "2026-06-28T07:30:00Z",
    reviewedBy: "editor@meridian.news",
    publishedAt: "2026-06-28T08:00:00Z",
    isLastKnownGood: true,
    etag: `seed-current-${id}`,
    lang: "en",
  };
}

export const SEED_CURRENT_IDS = SEED_META.map((m) => m.id);

export function buildDigest(issue: number): Digest {
  const byThis = [...SEED_META].sort((a, b) => a.thisRank - b.thisRank);
  return {
    issue,
    weekOf: "2026-06-22",
    store: "published",
    lede: "이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다.",
    reshuffle: SEED_META.map((m) => ({
      currentId: m.id,
      name: m.name,
      colorKey: m.id,
      lastRank: m.lastRank,
      thisRank: m.thisRank,
    })),
    movers: {
      climber: { currentId: "ai-governance", name: "AI governance", lastRank: 3, thisRank: 1, note: "규제 수렴 가속" },
      faller: { currentId: "middle-east", name: "Middle East", lastRank: 2, thisRank: 5, note: "긴장 완화" },
    },
    blurbs: byThis.slice(0, 3).map((m) => ({ kicker: m.name, body: m.blurb })),
    watchNext: [
      "AI 거버넌스: 다국적 표준 초안 발표 여부",
      "에너지: 전력망 투자 발표가 모멘텀을 굳히는지",
      "생활비: 고점 평탄화가 하강으로 전환되는지",
    ],
    stats: { currentsTracked: 12, newThreads: 3, storiesScanned: 184320 },
    lang: "en",
  };
}
