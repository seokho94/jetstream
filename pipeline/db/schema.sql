-- Meridian — Phase 0 schema (single source of truth: docs/design/data-model.md §3)
-- Apply: psql "$DATABASE_URL" -f pipeline/db/schema.sql
-- Requires: PostgreSQL 15+ with pgvector & pgcrypto extensions.

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
