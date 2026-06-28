// Jetstream data model — mirrors docs/design/data-model.md §2 (DDL-aligned).
// On conflict, docs/design/CANON.md §14 wins.

// ── shared enums (1:1 with DDL) ──
export type MomentumState = "rising" | "peaking" | "cooling" | "steady";
export type CurrentStatus = "active" | "merged" | "dormant";
export type SourceTier = "tier_1" | "tier_2" | "tier_3";
export type LicenseTier = "licensed" | "crawl_ttl" | "metadata_only";
export type LifecycleType = "spawn" | "split" | "merge" | "dormant" | "revive";
export type ViewStore = "draft" | "published";
export type CoverageAxis = "region_block" | "outlet_type"; // political-leaning labels avoided

// ── pipeline entities ──
export interface Vertical {
  id: string; // 'geopolitics'
  name: string;
  coverageAxes: CoverageAxis[];
}

export interface SourceRegistry {
  domain: string; // PK 'reuters.com'
  outletName: string;
  tier: SourceTier;
  country?: string; // ISO-3166 alpha-2
  regionBlock?: string; // 'EU' | 'MENA' | 'NA' ...
  outletType?: string; // 'wire' | 'newspaper' | 'broadcaster' | 'digital'
  leaning?: string; // internal only — never surfaced in coverage
  licenseTier: LicenseTier;
  bodyTtl?: string; // ISO-8601 duration; null = keep forever
  isWhitelisted: boolean;
}

export interface Article {
  id: string;
  url: string;
  canonicalUrl: string;
  sourceDomain: string; // FK source_registry.domain
  publishedAt: string; // ISO; partition key
  ingestedAt: string;
  language: string; // ISO-639-1
  title: string;
  lede?: string; // embedding target = title + lede
  body?: string; // nullable: degrade / purge
  bodyExtracted: boolean;
  sourceLicenseTier: LicenseTier;
  purgeAfter?: string;
  simhash?: string; // 64-bit
  isCanonical: boolean;
  canonicalArticleId?: string;
  embedding?: number[]; // vector(1024), canonical only
  embeddingVersion?: string; // 'bge-m3@v1.5'
  eventId?: string;
  countries?: string[];
  tone?: number;
}

export interface Event {
  id: string;
  currentId?: string;
  summary: string;
  firstSeen: string;
  lastSeen: string;
  articleCount: number; // canonical count → volume
  memberCount: number; // incl near-dup → spread
  countries: string[];
  outlets: string[];
  centroid: number[]; // vector(1024), EMA
  representativeArticleIds: string[];
  expiresAt: string; // lastSeen + 14d
}

export interface CoverageConfig {
  axis: CoverageAxis;
  minN: number; // default 5
  buckets: { label: string; match: Record<string, string> }[];
}

export interface Current {
  id: string; // stable slug 'middle-east'
  verticalId: string;
  name: string;
  colorKey: string; // FK color_registry.color_key
  status: CurrentStatus;
  mergedInto?: string;
  centroid?: number[]; // taxonomy anchor (append-only assignment)
  taxonomySeed?: string;
  coverageConfig: CoverageConfig;
}

export interface ArticleCurrent {
  currentId: string;
  articleId: string;
  articlePublishedAt: string;
  isPrimary: boolean; // false = secondary tag
  assignedAt: string;
}

export interface MomentumPoint {
  currentId: string;
  t: string; // date
  volume: number; // 7-day EMA
  persistenceDays: number;
  spread: number;
  spreadOutlets: number;
  spreadCountries: number;
  accelD1: number;
  accelD2: number;
  baselineMedian: number;
  baselineMad: number;
  score: number; // normalized weighted sum (ranking)
  state: MomentumState; // separate state signal
  tauState: number; // adaptive k*MAD
}

export interface WeeklyRank {
  issue: number;
  currentId: string;
  weekOf: string;
  rank: number; // shown fact → frozen
  score: number;
  state: MomentumState;
  capturedAt: string;
}

export interface CurrentLifecycleEvent {
  id: string;
  type: LifecycleType;
  currentId: string;
  relatedCurrentId?: string;
  occurredAt: string;
  evidence: Record<string, unknown>;
  actor: string; // 'system' | editor email
}

// ── published (read-optimized) objects ──
export interface ArcPoint {
  t: string;
  value: number; // server-normalized 0..1 (CANON R4)
  marker?: number; // 1..5; maps to TimelineNode.node
  eventId?: string;
}

export interface Citation {
  text: string;
  outlet: string;
  url: string;
  charStart: number;
  charEnd: number;
}

export interface TimelineNode {
  node: number; // 1..5, maps to arc marker
  date: string;
  text: string;
  eventId?: string;
  sources: Citation[];
  isLatest?: boolean;
}

export interface CoverageView {
  axis: CoverageAxis;
  minN: number;
  buckets: { label: string; pct: number; n: number }[];
  hidden: string[]; // hidden by min-n
}

export interface CurrentView {
  currentId: string;
  store: ViewStore;
  version: number;
  name: string;
  colorKey: string;
  rank: number;
  state: MomentumState;
  arc: ArcPoint[];
  brief: { whatsHappening: string; whyItMatters: string; citations: Citation[] };
  timeline: TimelineNode[];
  coverage: CoverageView;
  asOf: string;
  reviewedAt?: string;
  reviewedBy?: string;
  publishedAt?: string;
  isLastKnownGood: boolean;
  etag: string;
  lang: string; // CANON R12; Phase 0 'en'
}

export interface StreamgraphSeries {
  currentId: string;
  colorKey: string;
  series: { t: string; share: number }[]; // server-normalized
}

export interface RankedRow {
  currentId: string;
  name: string;
  colorKey: string;
  rank: number; // live from momentum_point.score
  state: MomentumState;
  score: number;
  sparkline: number[];
  attention: number; // 0..1
}

export interface DigestTeaser {
  issue: number;
  weekOf: string;
  lede: string;
}

export interface BoardView {
  id: number;
  asOf: string;
  generatedAt: string;
  isCurrent: boolean; // CANON R7 — drives stale badge
  todaysRead: { paragraph: string; asOf: string }; // CANON R9
  streamgraph: StreamgraphSeries[];
  ranked: RankedRow[];
  digestTeaser: DigestTeaser; // CANON R9
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
  etag: string;
  lang: string;
}

export interface Mover {
  currentId: string;
  name: string;
  lastRank: number;
  thisRank: number;
  note: string;
}

export interface Digest {
  issue: number;
  weekOf: string;
  store: ViewStore;
  lede: string;
  reshuffle: {
    currentId: string;
    name: string;
    colorKey: string;
    lastRank: number;
    thisRank: number;
  }[];
  movers: { climber: Mover; faller: Mover }; // CANON R9 (enriched)
  blurbs: { kicker: string; body: string }[];
  watchNext: string[];
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
  lang: string;
}

// ── search (CANON R14: Phase 0 = currents + grounded timeline events; ILIKE) ──
export interface SearchHit {
  type: "current" | "event";
  id: string;
  currentId: string;
  title: string;
  snippet: string;
  colorKey: string;
  state?: MomentumState | null;
  date?: string | null;
  url?: string | null;
}
