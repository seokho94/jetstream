# 데이터 모델

> **⚠️ 검수 반영(v2):** 본 문서는 [CANON](CANON.md) **§14 RESOLUTIONS**로 갱신됨 — 충돌 시 §14 최우선. 적용: **R1**(`current_status={active,merged,dormant}` ↔ 리뷰 상태머신 `review_state` 분리) · **R2**(`CurrentView.arc`=평탄 `ArcPoint[]`) · **R4**(`arc.value`=정규화 0..1, `momentum_point.volume`=raw) · **R5**(전용 ENUM `license_tier {full,snippet,metadata}`) · **R11**(`color_registry` 상태배지 4색 `is_reserved` 예약·충돌 hue 재배정) · **R12**(발행 뷰에 `lang` 컬럼·PK 포함).

> **목적:** §6의 모든 갭을 해소한 Jetstream 데이터 모델(TS 인터페이스 + Postgres DDL, schema.sql 수준). 모든 이름·타입·임계는 `canon`과 동일하며 충돌 시 canon이 이긴다.
> **적용 범위:** Phase 0(geopolitics·수동 current·8주 백필)에 즉시 적용. Phase 1(2버티컬·자동화)·Phase 2(자동 split/merge·확장)는 컬럼/임계 **추가만** 허용(의미 변경 금지).
> **스토리지:** 단일 Postgres + `pgvector`(임베딩·검색) + `momentum_point` 시간버킷 테이블. `article`는 월 RANGE 파티셔닝, 본문은 `license_tier`/`purge_after`로 수명 관리.

## 1. §6 대비 변경 요약

| 영역 | §6 (원본) | 개정 | 사유(ADR) |
|---|---|---|---|
| Vertical | 없음 | `vertical` 엔티티 + `current.vertical_id` | ADR-12 |
| 임베딩 버전 | `embedding: number[]`만 | `embedding vector(1024)` + `embedding_version`(필수, `bge-m3@v1.5`) | ADR-2 |
| 거리/인덱스 | 미지정 | pgvector HNSW, cosine | ADR-2 |
| 상태 | 3종(rising/peaking/cooling) | **4종**(+`steady`) ENUM `momentum_state` | ADR-3 |
| 모멘텀 필드 | volume/persistence/spread/accel/score/state | + `spread_outlets/countries`, `accel_d1/d2`, `baseline_median/mad`, `tau_state` | ADR-4 |
| 랭크 동결 | 없음 | `weekly_rank` 스냅샷(불변) | ADR-12 |
| split/merge | "explicit events"(미모델) | `current_lifecycle_event` 로그 테이블 | ADR-6 |
| article↔current | `eventId?` 단일 | `article_current` 다대다(`is_primary` 보조태그) | ADR-12 |
| 소스 메타 | `source: string` | `source_registry`(domain/tier/country/region_block/outlet_type/leaning/license_tier) | ADR-1/9 |
| 본문 수명/파티션 | `body: string` | `source_license_tier`/`purge_after` + 월 파티셔닝 | ADR-1 |
| dedup | 없음 | `canonical_url`/`simhash`/`is_canonical`/`canonical_article_id` | ADR-7 |
| arc↔timeline | 분리 | `arc[].marker`=`timeline[].node`(1..5)+공유 `eventId` | ADR-12 |
| 발행 board | 없음(CurrentView/Digest만) | `board_view`(+ `todays_read`) 발행 객체 | ADR-5 |
| coverage 정의 | `buckets`만 | `current.coverage_config`(정의) + `current_view.coverage`(산출, min-n/hidden) | ADR-9 |
| 발행 2-store | 단일 | `current_view.store`(draft/published)+`is_last_known_good`, `editorial_audit` | ADR-10 |
| 색 | 6 토큰 | `color_registry`(12+예비, FK) | ADR-11 |

## 2. TypeScript 인터페이스

```ts
// ── 공통 enum (DDL과 1:1) ──
export type MomentumState = "rising" | "peaking" | "cooling" | "steady";
export type CurrentStatus = "active" | "merged" | "dormant";
export type SourceTier   = "tier_1" | "tier_2" | "tier_3";
export type LicenseTier   = "licensed" | "crawl_ttl" | "metadata_only";
export type LifecycleType  = "spawn" | "split" | "merge" | "dormant" | "revive";
export type ViewStore      = "draft" | "published";
export type CoverageAxis   = "region_block" | "outlet_type"; // 정치성향 라벨 회피

// ── 파이프라인 엔티티 ──
export interface Vertical {
  id: string;                 // 'geopolitics'
  name: string;
  coverageAxes: CoverageAxis[]; // 기본 ['region_block','outlet_type']
}

export interface SourceRegistry {
  domain: string;             // PK 'reuters.com'
  outletName: string;
  tier: SourceTier;
  country?: string;           // ISO-3166 alpha-2
  regionBlock?: string;       // coverage: 'EU'|'MENA'|'NA'...
  outletType?: string;        // 'wire'|'newspaper'|'broadcaster'|'digital'
  leaning?: string;           // 내부 전용, coverage에 미노출
  licenseTier: LicenseTier;
  bodyTtl?: string;           // ISO-8601 duration; null=영구 보존
  isWhitelisted: boolean;     // 300~500 신뢰 크롤 집합
}

export interface Article {
  id: string;                 // uuid
  url: string;
  canonicalUrl: string;       // 정규화
  sourceDomain: string;       // FK source_registry.domain
  publishedAt: string;        // ISO; 파티션 키
  ingestedAt: string;
  language: string;           // ISO-639-1, 감지값
  title: string;
  lede?: string;              // 임베딩 대상 (title+lede)
  body?: string;              // nullable: degrade/purge
  bodyExtracted: boolean;     // trafilatura/readability 성공
  sourceLicenseTier: LicenseTier;
  purgeAfter?: string;        // crawl_ttl 본문 폐기 기한
  simhash?: string;           // 64-bit, bigint 직렬화
  isCanonical: boolean;       // false=near-dup 멤버
  canonicalArticleId?: string;
  embedding?: number[];       // vector(1024), 정본만
  embeddingVersion?: string;  // 'bge-m3@v1.5'
  eventId?: string;           // 배정 이벤트 (app-FK)
  countries?: string[];       // GDELT geo
  tone?: number;              // GDELT tone
}

export interface Event {
  id: string;
  currentId?: string;
  summary: string;
  firstSeen: string;
  lastSeen: string;
  articleCount: number;       // 정본 수 → volume 근거
  memberCount: number;        // near-dup 포함 → spread 근거
  countries: string[];
  outlets: string[];
  centroid: number[];         // vector(1024), EMA
  representativeArticleIds: string[]; // LLM 코퍼스 1~2건
  expiresAt: string;          // lastSeen + 14d
}

export interface Current {
  id: string;                 // 안정 슬러그 'middle-east'
  verticalId: string;         // FK vertical.id
  name: string;               // LLM-named, 인간 승인
  colorKey: string;           // FK color_registry.color_key
  status: CurrentStatus;
  mergedInto?: string;
  centroid?: number[];        // 택소노미 앵커 (append-only 배정)
  taxonomySeed?: string;
  coverageConfig: {           // coverage 정의 저장 위치
    axis: CoverageAxis;
    minN: number;             // 기본 5
    buckets: { label: string; match: Record<string, string> }[];
  };
}

export interface ArticleCurrent {  // 다대다 조인
  currentId: string;
  articleId: string;
  articlePublishedAt: string; // 파티션 프루닝
  isPrimary: boolean;         // false=보조 태그
  assignedAt: string;
}

export interface MomentumPoint {
  currentId: string;
  t: string;                  // date
  volume: number;             // 7일 EMA
  persistenceDays: number;    // 1~2일 결손 허용
  spread: number;             // outlet+country 다양성
  spreadOutlets: number;
  spreadCountries: number;
  accelD1: number;            // 7일 도함수
  accelD2: number;            // 14일 2차 도함수
  baselineMedian: number;     // 60~90일 robust
  baselineMad: number;
  score: number;              // 정규화 가중합 (랭킹)
  state: MomentumState;       // 분리된 상태 신호
  tauState: number;           // 적응 임계 k*MAD
}

export interface WeeklyRank {  // 동결 스냅샷
  issue: number;
  currentId: string;
  weekOf: string;
  rank: number;               // 보여진 사실 → 불변
  score: number;
  state: MomentumState;
  capturedAt: string;
}

export interface CurrentLifecycleEvent {
  id: string;
  type: LifecycleType;
  currentId: string;
  relatedCurrentId?: string;  // split-to / merge-into
  occurredAt: string;
  evidence: Record<string, unknown>;
  actor: string;              // 'system' | editor email
}

// ── 발행(read-optimized) 객체 ──
export interface ArcPoint { t: string; value: number; marker?: number; eventId?: string; } // marker 1..5
export interface TimelineNode {
  node: number;               // 1..5, arc marker와 매핑
  date: string;
  text: string;
  eventId?: string;
  sources: { outlet: string; url: string; charStart: number; charEnd: number }[]; // Citations 하드바인딩
}
export interface CoverageView {
  axis: CoverageAxis;
  minN: number;
  buckets: { label: string; pct: number; n: number }[];
  hidden: string[];           // min-n 미달로 숨김
}

export interface CurrentView { // current_view, store별
  currentId: string;
  store: ViewStore;
  version: number;
  name: string;
  colorKey: string;
  rank: number;
  state: MomentumState;
  arc: ArcPoint[];
  brief: { whatsHappening: string; whyItMatters: string;
           citations: { text: string; outlet: string; url: string; charStart: number; charEnd: number }[] };
  timeline: TimelineNode[];
  coverage: CoverageView;
  asOf: string;
  reviewedAt?: string;
  reviewedBy?: string;
  publishedAt?: string;
  isLastKnownGood: boolean;
  etag: string;
}

export interface BoardView {  // GET /v1/board 단일 콜
  id: number;
  asOf: string;               // 신선도 노출
  generatedAt: string;
  todaysRead: { text: string; asOf: string };
  streamgraph: { currentId: string; series: { t: string; share: number }[] }[]; // 서버 정규화 share
  ranked: { currentId: string; name: string; colorKey: string; rank: number;
            state: MomentumState; score: number; sparkline: number[]; attention: number }[];
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
  etag: string;
}

export interface Digest {
  issue: number;
  weekOf: string;
  store: ViewStore;
  lede: string;
  reshuffle: { currentId: string; name: string; colorKey: string; lastRank: number; thisRank: number }[]; // weekly_rank 기반
  movers: { climberId: string; fallerId: string };
  blurbs: { kicker: string; body: string }[];
  watchNext: string[];
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
}
```

## 3. Postgres DDL (schema.sql)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ── enums ──
CREATE TYPE momentum_state       AS ENUM ('rising','peaking','cooling','steady');
CREATE TYPE current_status        AS ENUM ('active','merged','dormant');
CREATE TYPE source_tier           AS ENUM ('tier_1','tier_2','tier_3');
CREATE TYPE license_tier          AS ENUM ('licensed','crawl_ttl','metadata_only');
CREATE TYPE lifecycle_event_type  AS ENUM ('spawn','split','merge','dormant','revive');
CREATE TYPE view_store            AS ENUM ('draft','published');
CREATE TYPE coverage_axis         AS ENUM ('region_block','outlet_type');

-- ── 색 레지스트리 (12 활성 + 예비, current.color_key의 FK 대상) ──
CREATE TABLE color_registry (
  color_key   text PRIMARY KEY,
  hex         char(7) NOT NULL,
  hue_name    text NOT NULL,
  is_reserved boolean NOT NULL DEFAULT false
);
-- ── 활성 current hue (충돌 해소 확정 · CANON §14 R11) ──
INSERT INTO color_registry(color_key, hex, hue_name) VALUES
  ('ai-governance','#C46BD8','orchid'),  ('cost-of-living','#E86A8E','rose'),   -- 재배정(was amber/coral)
  ('energy','#9CCB3B','lime'),           ('middle-east','#5C6BC0','indigo'),    -- 재배정(was teal/steel)
  ('china','#4EA8DE','blue'),            ('climate','#8B7FE8','violet'),        -- 유지
  -- Phase 1+ 후보 hue (실제 배정 시 ΔE·WCAG·colorblind QA 게이트 통과 조건)
  ('elections','#D9C24A','mustard'),     ('trade','#D85FB0','magenta'),
  ('migration','#3FB6C9','cyan'),        ('tech-platforms','#A074E6','purple'),
  ('markets','#3FBE86','emerald'),       ('defense','#C77A6A','clay');

-- ── 예약 시스템 색 (current 배정 금지 · is_reserved=true) ──
INSERT INTO color_registry(color_key, hex, hue_name, is_reserved) VALUES
  ('state-rising','#F5A524','amber',true),   ('state-peaking','#FB7A50','coral',true),
  ('state-cooling','#7C9CC0','steel',true),  ('state-steady','#9BA3AF','muted',true),
  ('brand-teal','#34D0BA','teal',true),      ('up-green','#6FBF73','green',true),
  ('down-red','#D08585','red',true),         ('other-grey','#586170','slate',true);  -- streamgraph 'Other'(R8)

-- ── vertical ──
CREATE TABLE vertical (
  id            text PRIMARY KEY,                 -- 'geopolitics'
  name          text NOT NULL,
  coverage_axes coverage_axis[] NOT NULL DEFAULT '{region_block,outlet_type}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ── source_registry (화이트리스트·tier·license) ──
CREATE TABLE source_registry (
  domain         text PRIMARY KEY,                -- 'reuters.com'
  outlet_name    text NOT NULL,
  tier           source_tier NOT NULL,
  country        char(2),                         -- ISO-3166 alpha-2
  region_block   text,                            -- coverage용
  outlet_type    text,                            -- 'wire'|'newspaper'|'broadcaster'|'digital'
  leaning        text,                            -- 내부 전용, coverage 미노출
  license_tier   license_tier NOT NULL DEFAULT 'metadata_only',
  body_ttl       interval,                        -- null=영구; purge_after = ingested_at + body_ttl
  is_whitelisted boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- ── current (안정 ID, 택소노미 앵커) ──
CREATE TABLE current (
  id              text PRIMARY KEY,               -- 'middle-east'
  vertical_id     text NOT NULL REFERENCES vertical(id),
  name            text NOT NULL,
  color_key       text NOT NULL REFERENCES color_registry(color_key),
  status          current_status NOT NULL DEFAULT 'active',
  merged_into     text REFERENCES current(id),
  centroid        vector(1024),                   -- append-only 배정용
  taxonomy_seed   text,
  coverage_config jsonb NOT NULL DEFAULT '{}',    -- axis/min_n/bucket 정의
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_current_vertical ON current(vertical_id);

-- ── article (월 RANGE 파티셔닝; PK에 파티션키 포함) ──
CREATE TABLE article (
  id                  uuid NOT NULL DEFAULT gen_random_uuid(),
  url                 text NOT NULL,
  canonical_url       text NOT NULL,
  source_domain       text NOT NULL REFERENCES source_registry(domain),
  published_at        timestamptz NOT NULL,
  ingested_at         timestamptz NOT NULL DEFAULT now(),
  language            char(2) NOT NULL,
  title               text NOT NULL,
  lede                text,
  body                text,
  body_extracted      boolean NOT NULL DEFAULT false,
  source_license_tier license_tier NOT NULL,
  purge_after         timestamptz,                -- crawl_ttl 본문 폐기 기한
  simhash             bigint,                     -- 64-bit body SimHash
  is_canonical        boolean NOT NULL DEFAULT true,
  canonical_article_id uuid,
  embedding           vector(1024),               -- 정본만 (그 외 NULL)
  embedding_version   text,                       -- 'bge-m3@v1.5'
  event_id            uuid,                       -- app-FK event.id
  countries           char(2)[],
  tone                real,
  PRIMARY KEY (id, published_at)
) PARTITION BY RANGE (published_at);

-- 월 파티션 예시 (8주 백필 → 운영시 자동 생성 잡)
CREATE TABLE article_2026_05 PARTITION OF article
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE article_2026_06 PARTITION OF article
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- HNSW(cosine)는 파티션마다 생성; 교차파티션 ANN은 파티션 결과 union
-- (Phase 0/1 볼륨에서 수용, Phase 2 재검토). 정본만 색인되도록 부분인덱스.
CREATE INDEX idx_article_2026_05_hnsw ON article_2026_05
  USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
  WHERE is_canonical AND embedding IS NOT NULL;
CREATE INDEX idx_article_2026_06_hnsw ON article_2026_06
  USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
  WHERE is_canonical AND embedding IS NOT NULL;
CREATE INDEX idx_article_event ON article(event_id);
CREATE INDEX idx_article_canurl ON article(canonical_url);

-- ── event (leader-follower, 14일 만료) ──
CREATE TABLE event (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  current_id               text REFERENCES current(id),
  summary                  text,
  first_seen               timestamptz NOT NULL,
  last_seen                timestamptz NOT NULL,
  article_count            int NOT NULL DEFAULT 0,   -- 정본 → volume
  member_count             int NOT NULL DEFAULT 0,   -- near-dup 포함 → spread
  countries                char(2)[] NOT NULL DEFAULT '{}',
  outlets                  text[] NOT NULL DEFAULT '{}',
  centroid                 vector(1024) NOT NULL,
  centroid_updated_at      timestamptz NOT NULL DEFAULT now(),
  representative_article_ids uuid[] NOT NULL DEFAULT '{}', -- LLM 코퍼스 1~2건
  expires_at               timestamptz NOT NULL,     -- last_seen + 14d
  created_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_event_current ON event(current_id);
CREATE INDEX idx_event_hnsw ON event
  USING hnsw (centroid vector_cosine_ops) WITH (m=16, ef_construction=64);

-- ── article ↔ current 다대다 (보조 태그 허용) ──
CREATE TABLE article_current (
  current_id            text NOT NULL REFERENCES current(id),
  article_id            uuid NOT NULL,
  article_published_at  timestamptz NOT NULL,       -- 파티션 프루닝, app-FK
  is_primary            boolean NOT NULL DEFAULT true,
  assigned_at           timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (current_id, article_id)
);
CREATE INDEX idx_artcur_article ON article_current(article_id);

-- ── momentum_point (current x day) ──
CREATE TABLE momentum_point (
  current_id        text NOT NULL REFERENCES current(id),
  t                 date NOT NULL,
  volume            real NOT NULL,    -- 7일 EMA
  persistence_days  int  NOT NULL,    -- 1~2일 결손 허용
  spread            real NOT NULL,
  spread_outlets    int  NOT NULL,
  spread_countries  int  NOT NULL,
  accel_d1          real NOT NULL,    -- 7일 도함수
  accel_d2          real NOT NULL,    -- 14일 2차
  baseline_median   real NOT NULL,    -- 60~90일 robust
  baseline_mad      real NOT NULL,
  score             real NOT NULL,    -- 0.30*z_accel+0.30*z_persist+0.25*z_vol+0.15*z_spread
  state             momentum_state NOT NULL,
  tau_state         real NOT NULL,    -- k*MAD (k=1.0)
  PRIMARY KEY (current_id, t)
);

-- ── weekly_rank (동결 스냅샷) ──
CREATE TABLE weekly_rank (
  issue       int  NOT NULL,
  current_id  text NOT NULL REFERENCES current(id),
  week_of     date NOT NULL,
  rank        int  NOT NULL,          -- 보여진 사실 → 불변
  score       real NOT NULL,
  state       momentum_state NOT NULL,
  captured_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (issue, current_id)
);
CREATE INDEX idx_weeklyrank_current ON weekly_rank(current_id);

-- ── split/merge/dormant 명시 로그 ──
CREATE TABLE current_lifecycle_event (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type               lifecycle_event_type NOT NULL,
  current_id         text NOT NULL REFERENCES current(id),
  related_current_id text REFERENCES current(id),   -- split-to / merge-into
  occurred_at        timestamptz NOT NULL DEFAULT now(),
  evidence           jsonb NOT NULL DEFAULT '{}',
  actor              text NOT NULL DEFAULT 'system'
);
CREATE INDEX idx_lifecycle_current ON current_lifecycle_event(current_id, occurred_at);

-- ── current_view (Draft/Published 2-store + last-known-good) ──
CREATE TABLE current_view (
  current_id         text NOT NULL REFERENCES current(id),
  store              view_store NOT NULL,
  version            int NOT NULL,
  name               text NOT NULL,
  color_key          text NOT NULL,
  rank               int NOT NULL,
  state              momentum_state NOT NULL,
  arc                jsonb NOT NULL,   -- [{t,value,marker(1..5)?,eventId?}]
  brief              jsonb NOT NULL,   -- {whatsHappening,whyItMatters,citations:[{text,outlet,url,charStart,charEnd}]}
  timeline           jsonb NOT NULL,   -- [{node(1..5),date,text,eventId,sources:[{outlet,url,charStart,charEnd}]}]
  coverage           jsonb NOT NULL,   -- {axis,minN,buckets:[{label,pct,n}],hidden:[...]}
  as_of              timestamptz NOT NULL,
  reviewed_at        timestamptz,
  reviewed_by        text,
  published_at       timestamptz,
  is_last_known_good boolean NOT NULL DEFAULT false,
  etag               text NOT NULL,
  PRIMARY KEY (current_id, store, version)
);
-- current당 최신 published 1건만 last-known-good
CREATE UNIQUE INDEX uq_current_view_lkg ON current_view(current_id)
  WHERE store='published' AND is_last_known_good;

-- ── board_view (발행 객체 + today's read) ──
CREATE TABLE board_view (
  id           bigserial PRIMARY KEY,
  as_of        timestamptz NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now(),
  todays_read  jsonb NOT NULL,         -- {text, asOf}
  streamgraph  jsonb NOT NULL,         -- 서버 정규화 share [{currentId,series:[{t,share}]}]
  ranked       jsonb NOT NULL,         -- [{currentId,name,colorKey,rank,state,score,sparkline,attention}]
  stats        jsonb NOT NULL,
  is_current   boolean NOT NULL DEFAULT true,
  etag         text NOT NULL
);
CREATE UNIQUE INDEX uq_board_view_current ON board_view(is_current) WHERE is_current;

-- ── digest (주간 발행) ──
CREATE TABLE digest (
  issue        int PRIMARY KEY,
  week_of      date NOT NULL,
  store        view_store NOT NULL DEFAULT 'draft',
  lede         text NOT NULL,
  reshuffle    jsonb NOT NULL,         -- weekly_rank 기반 [{currentId,name,colorKey,lastRank,thisRank}]
  movers       jsonb NOT NULL,         -- {climberId,fallerId}
  blurbs       jsonb NOT NULL,
  watch_next   text[] NOT NULL,
  stats        jsonb NOT NULL,
  published_at timestamptz,
  etag         text
);

-- ── editorial_audit (append-only) ──
CREATE TABLE editorial_audit (
  id         bigserial PRIMARY KEY,
  at         timestamptz NOT NULL DEFAULT now(),
  actor      text NOT NULL,
  current_id text,
  field      text NOT NULL,            -- 'name'|'brief'|'timeline'|'coverage'|'publish'|'unpublish'
  action     text NOT NULL,            -- 'edit'|'approve'|'publish'|'rollback'|'unpublish'
  before     jsonb,
  after      jsonb,
  request_id text
);
CREATE INDEX idx_audit_current ON editorial_audit(current_id, at);
```

## 4. 무결성·운영 주석 (구속력)
- **파티션 FK:** Postgres는 파티션 테이블 FK에 파티션키 동반을 요구하므로 `article_current.article_id`·`article.canonical_article_id`·`article.event_id`는 **app-레벨 FK**(파티션 프루닝용 `article_published_at` 동반). `current_view`/`board_view`/`digest`/`momentum_point`의 FK는 DB 강제.
- **dedup 불변식:** `is_canonical=false` 행은 `embedding IS NULL` 그리고 `canonical_article_id IS NOT NULL`. volume=정본 수(`event.article_count`), spread=멤버 수(`event.member_count`)에서 산출.
- **본문 수명:** `license_tier='licensed'` → `purge_after=NULL`(영구); `'crawl_ttl'` → `purge_after=ingested_at+source_registry.body_ttl`(폐기 잡이 `body`만 NULL화, 메타/임베딩 유지); `'metadata_only'` → `body`/`lede` 미저장, 임베딩은 title 단독.
- **arc↔timeline:** `current_view.arc[].marker`(1..5) = `current_view.timeline[].node`(1..5), 양측 `eventId` 동일.
- **랭크 동결:** `weekly_rank`는 발행 시점 1회 기록 후 불변; digest `reshuffle`은 이 테이블만 조회(재계산 금지).
- **발행 일관성:** 클라는 `store='published'`만 조회. high-risk 필드(name/brief/timeline/coverage) verifier 실패 시 published 미갱신(fail-closed)·`is_last_known_good` 서빙; low-risk 실패는 fail-open. 모든 변이는 `editorial_audit` 기록.
- **상수:** 임베딩 `bge-m3@v1.5`/1024/cosine/HNSW(m=16,ef_construction=64,ef_search=100); dedup SimHash Hamming≤3; 클러스터 τ=0.84(0.82~0.86)·top-k=20·centroid α=0.2·14일 만료; 모멘텀 EMA 7일·persistence gap≤2일·baseline 60~90일·가중치 .30/.30/.25/.15·tau_state=k·MAD(k=1.0)·hysteresis 2일/dead-band 0.7; coverage min-n=5; LLM 본문 2.5k·current 캡 60k·모델 claude-sonnet-4-6/claude-opus-4-8; ISR 180s·폴링 60s.