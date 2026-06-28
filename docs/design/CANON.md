CANON — Meridian Phase 0 확정값 (하위 문서는 이 이름·값·상수를 그대로 재사용한다. 충돌 시 canon이 이긴다.)

## 0. 적용 범위
- Phase 0: vertical 1개(`geopolitics`), 수동 큐레이션 current ~10개, 8주 백필. 본 canon 전체가 구속력.
- Phase 1: vertical 2개(+`technology`), 온라인 클러스터링·LLM 합성·휴먼게이트 자동화. canon 동일 적용.
- Phase 2: split/merge 자동 발견(Jaccard-Hungarian), 다소스/다언어 확장. canon은 상위 호환(컬럼·임계 추가만 허용, 의미 변경 금지).

## 1. Embedding (LOCK)
- 모델: **BGE-M3** (default). 식별자 `EMBED_MODEL=bge-m3`, `EMBED_REVISION=v1.5`.
- 차원: **1024**. 거리척도: **cosine** (`vector_cosine_ops`).
- 대상 텍스트: **title + lede** (lede = 본문 첫 1~2문장/리드 단락, 추출 실패 시 title 단독).
- **원문 언어 직접 임베딩**(번역 후 임베딩 금지).
- 컬럼: `article.embedding vector(1024)`, `article.embedding_version text`(형식 `"<model>@<revision>"`, 예 `"bge-m3@v1.5"`). version 컬럼 필수.
- 인덱스: pgvector **HNSW**, `m=16, ef_construction=64`, 질의 `ef_search=100`. 임베딩은 dedup 정본(`is_canonical=true`)에만 존재(그 외 NULL).

## 2. 상태 집합 — 정식 4상태 (LOCK, §3/§6/Appendix 모순 해소)
ENUM `momentum_state = {rising, peaking, cooling, steady}`.
- `rising`: 가속(d1>0, d2≥0). 배지 amber `#F5A524` + `ti-trending-up`.
- `peaking`: 높지만 평탄화(d1≈0, d2<0, 최근 피크 부근). 배지 coral `#FB7A50` + `ti-activity`.
- `cooling`: 감속(d1<0). 배지 steel `#7C9CC0` + `ti-trending-down`.
- `steady`: 위 어느 트리거도 아님(베이스라인 부근 지속, 중립). 배지 muted `#9BA3AF` + `ti-minus`.
- 색 단독 인코딩 금지 → 항상 아이콘+라벨 동반.

## 3. Momentum / 정규화 (LOCK)
- `volume` = 일별 정본 기사수의 **7일 EMA**.
- `persistence_days` = 흐름 자기 robust baseline(median) 초과 **연속일수**, 1~2일 결손 허용 후 리셋(`PERSIST_GAP_TOL=2`).
- `spread` = 신디케이션 접은 후 **outlet·country 다양성**(`spread_outlets`, `spread_countries` 별도 보존).
- `accel_d1` = 7일 1차도함수, `accel_d2` = 14일 2차도함수.
- robust baseline = 흐름내 **60~90일(default 90)** trailing median/MAD.
- 정규화: 흐름내 `log1p(volume)` + robust z `z=(x-median)/(1.4826*MAD)` (각 성분 volume/persistence/spread/accel) → 흐름간·버티컬간 재표준화.
- **랭킹 점수(score)** = 정규화 가중합 `0.30*z_accel + 0.30*z_persist + 0.25*z_vol + 0.15*z_spread` (가중치 `W_ACCEL=.30, W_PERSIST=.30, W_VOLUME=.25, W_SPREAD=.15`). board/weekly_rank 순위는 이 score 내림차순.
- **랭킹점수 ≠ 상태신호**(분리). 상태는 accel 형태 분류기로 별도 산출.
- 상태 임계 `tau_state` = 흐름별 `k*MAD` (`STATE_K=1.0`). hysteresis: 진입 `tau_enter`, 이탈 `tau_exit=0.7*tau_enter`(dead-band), 상태 전환은 **2일 연속** 충족 시 확정(`STATE_HYSTERESIS_DAYS=2`).

## 4. Clustering / current ID 안정성 (LOCK)
- 온라인 **leader-follower**: pgvector HNSW top-k(`CLUSTER_TOPK=20`) → cosine sim **τ 컷 `TAU_CLUSTER=0.84` (범위 0.82~0.86)**.
- 이벤트 centroid **EMA `CENTROID_ALPHA=0.2`**, **14일 윈도 만료**(`CLUSTER_WINDOW_DAYS=14`, `event.expires_at = last_seen + 14d`).
- current ID 안정성: **Phase 1 = 하향식 택소노미 + append-only 배정**(매주 재군집 금지, 구조적 불변).
- split/merge/dormant = **명시 이벤트 로그** `current_lifecycle_event`(type ∈ `{spawn,split,merge,dormant,revive}`).
- Phase 2에서 Jaccard-Hungarian 자동 발견.

## 5. 사전 dedup (LOCK)
- canonical URL 정규화(소문자 host, fragment·`utm_*`·추적 파라미터 제거, query 정렬, AMP 해소) → `canonical_url`.
- 본문 **64-bit SimHash** near-dup, **Hamming ≤ 3** (`SIMHASH_HAMMING_MAX=3`) 군집화.
- 군집당 정본 1건만 임베딩(`is_canonical=true`); 나머지는 `canonical_article_id`로 연결, outlet/country 멤버십만 보존 → **spread엔 반영, volume=1**.

## 6. 핵심 테이블·키·신규 필드 (LOCK, 식별자 고정)
- `vertical(id PK, name, coverage_axes coverage_axis[])`.
- `source_registry(domain PK, outlet_name, tier source_tier, country, region_block, outlet_type, leaning[내부전용·미노출], license_tier, body_ttl, is_whitelisted)`.
- `article(PK (id, published_at), 월 RANGE 파티셔닝)`: `canonical_url, source_domain FK→source_registry, language, title, lede, body(nullable), body_extracted, source_license_tier license_tier, purge_after, simhash, is_canonical, canonical_article_id, embedding vector(1024), embedding_version, event_id(app-FK), countries, tone`.
- `event(id PK)`: `current_id FK→current, summary, first_seen, last_seen, article_count(정본·volume근거), member_count(near-dup포함·spread근거), countries, outlets, centroid vector(1024), representative_article_ids(LLM 코퍼스 1~2건), expires_at`.
- `current(id PK text 슬러그·주차간 안정)`: `vertical_id FK→vertical, name, color_key FK→color_registry, status current_status, merged_into FK→current, centroid vector(1024), taxonomy_seed, coverage_config jsonb`.
- `article_current(PK (current_id, article_id))` 다대다: `article_published_at(파티션 프루닝·app-FK), is_primary(보조태그=false)`.
- `momentum_point(PK (current_id, t))`: 위 §3 모든 산출(`volume, persistence_days, spread, spread_outlets, spread_countries, accel_d1, accel_d2, baseline_median, baseline_mad, score, state, tau_state`).
- `weekly_rank(PK (issue, current_id))`: `week_of, rank, score, state, captured_at` — 랭크는 '보여진 사실'로 **동결**(불변).
- `current_lifecycle_event(id PK)`: `type lifecycle_event_type, current_id, related_current_id, occurred_at, evidence jsonb, actor`.
- `current_view(PK (current_id, store, version))` Draft/Published 2-store: `store view_store, rank, state, color_key, arc jsonb, brief jsonb, timeline jsonb, coverage jsonb, as_of, reviewed_at, reviewed_by, published_at, is_last_known_good, etag`.
- `board_view(id PK)` 발행 객체: `as_of, generated_at, todays_read jsonb, streamgraph jsonb(서버 정규화 share), ranked jsonb, stats jsonb, is_current, etag`.
- `digest(issue PK)`: `week_of, store, lede, reshuffle jsonb, movers jsonb, blurbs jsonb, watch_next, stats jsonb, published_at, etag`.
- `color_registry(color_key PK, hex, hue_name, is_reserved)`.
- `editorial_audit(id PK)` append-only: `at, actor, current_id, field, action, before, after, request_id`.
- arc↔timeline 매핑: `arc[].marker`(1..5) = `timeline[].node`(1..5), 양쪽 `eventId` 공유.

## 7. API (LOCK)
- 스타일: **REST + 뷰별 BFF**(GraphQL 불채택).
- 엔드포인트: `GET /v1/board`, `GET /v1/currents/{id}`, `GET /v1/digests/{issue}`, `GET /v1/search?q=`.
- `/v1/board`는 단일 `BoardView` 1콜, streamgraph **share는 서버에서 정규화**(클라 비계산).
- ETag/HTTP 캐시 + ISR(`ISR_REVALIDATE=180s`, 범위 120~300), 응답에 **`asOf`** 신선도 노출. 클라 폴링 `POLL_INTERVAL=60s`.

## 8. 차트/클라이언트 (LOCK)
- **순수 SVG + d3-shape**(SSR·접근성·테스트 용이). 호버 의존 금지, 탭타깃 **≥44px**.
- 다크테마 WCAG 대비(비텍스트 3:1), 색 단독 인코딩 금지(아이콘+라벨). 차트마다 스크린리더용 **데이터 테이블 대체** 제공.
- colorKey 팔레트: `color_registry`가 단일 진실원. 활성 12색(+예비 3, 최대 15), current당 hue 동결·중앙 거버넌스 배정(append-only). 모멘텀 의미색(up-green `#6FBF73`/down-red `#D08585`)과 충돌 hue 제외, colorblind+대비 QA 게이트 통과.

## 9. LLM 합성 (LOCK)
- 모델: 기본 **`claude-sonnet-4-6`**, 최난도 **`claude-opus-4-8`**(현행 ID 확인 완료).
- 코퍼스: current당 이벤트별 대표 1~2건, 본문 트렁케이션 `LLM_BODY_TOK=2500`(범위 2~3k), current당 총 캡 `LLM_CURRENT_TOK_CAP=60000`. system+instruction **prefix 고정 → prompt caching**.
- brief/timeline은 **Citations API**로 인용을 소스 **char span**에 하드바인딩(환각 인용 차단). 발행 전 **verifier**가 인용 스팬 밖 고유명사·수치 스팟체크.

## 10. coverage 'How it's covered' (LOCK)
- 축: 검증가능 메타데이터 **결정적 룩업 1순위** — `coverage_axis = {region_block, outlet_type}`(정치성향 라벨 회피, LLM은 프레이밍 보조).
- outlet-unique + 신디케이션 접기. **min-n 미달 막대 숨김**(`COVERAGE_MIN_N=5`). 버킷 정의는 `current.coverage_config`에 저장, 산출 결과는 `current_view.coverage`.

## 11. 휴먼 게이트 (LOCK)
- **Draft/Published 2-store** + last-known-good 노출(`current_view.is_last_known_good`).
- 필드 편집권한 매트릭스: `name`=후보택일(자유입력 시 2차 승인), `brief`=인라인 교정, `timeline`=인라인 교정, `coverage`=잠금(읽기전용), `color_key`=레지스트리 잠금.
- 위험도: high-risk(name/brief/timeline/coverage) **fail-closed**(검증 실패 시 발행 차단), low-risk(색·정렬 등) **fail-open**(last-known-good 서빙). SLA·롤백·긴급 unpublish·append-only 감사(`editorial_audit`).

## 12. 보안 (cross-cutting, LOCK)
- 신뢰불가 기사 본문 → LLM **프롬프트 인젝션 방지**(본문은 데이터 채널로만, 인용 스팬 검증, 명령 무시 가드).
- 크롤링 **SSRF 가드**(화이트리스트 도메인만, IP/리다이렉트/사설망 차단).
- 에디터 툴 **authn/authz**(필드별 권한, 모든 변이 감사로그).

## 13. Go/No-Go 수치 (Phase 0)
- 클러스터 purity(샘플 수동평가) ≥ 0.80; current ID churn = 0(append-only 구조 보장).
- 상태-인간판단 일치 ≥ 70%(current-week 샘플); coverage 결정적 룩업 비율 ≥ 95%.
- 인용 유효성 100%(모든 인용 소스 스팬 해소); verifier 환각 플래그 < 5%(발행 전).
- board p95 staleness ≤ 5분(활성시간); 에디터 10 current 검수 < 30분/일.

---

## 14. RESOLUTIONS (검수 반영 v2 — 위 절과 충돌 시 본 절이 최우선)

검수에서 발견된 문서 간 불일치·누락을 확정 해소한다. 하위 문서는 본 절을 그대로 따른다.

- **R1 — current_status vs review_state 분리(LOCK):** `current_status` ENUM = `{active, merged, dormant}` (current 생애주기) 전용. 리뷰/발행 상태머신은 **별도 ENUM `review_state`** = `{synthesizing, pending_review, changes_requested, approved, published, blocked, unpublished}`. 둘을 같은 타입명으로 재사용 금지.
- **R2 — arc 형태(LOCK):** `current_view.arc` = **평탄 배열** `ArcPoint[] = { t:string; value:number; marker?:1|2|3|4|5; eventId?:string }`. 대부분 점은 marker 없음. marker(1..5)를 가진 ≤5개 점만 `timeline[].node`와 공유 `eventId`로 매핑.
- **R3 — board 랭킹 출처(LOCK):** `board_view.ranked[].rank`는 생성 시점 **live** = `RANK() OVER (ORDER BY momentum_point.score DESC)`. `weekly_rank`(동결)는 **digest.reshuffle 전용**. board의 score·rank 모두 live `momentum_point`에서.
- **R4 — arc.value 스케일(LOCK):** `momentum_point.volume`은 **raw**(7일 EMA, 절대수) 유지. 발행되는 `current_view.arc[].value`는 **서버 정규화 attention [0,1]**(sparkline·attention bar와 일관). momentum-engine은 arc.value를 '정규화 표시값'으로 명시(raw EMA 아님).
- **R5 — license_tier(LOCK):** 전용 ENUM `license_tier = {licensed, crawl_ttl, metadata_only}`. licensed=본문 영구 저장(`purge_after=NULL`); crawl_ttl=크롤 본문 저장 후 `purge_after=ingested_at+body_ttl`에 **본문만** 폐기(메타·임베딩 유지); metadata_only=본문 미저장(임베딩은 title 단독). `source_registry.license_tier`·`article.source_license_tier` 모두 `license_tier` 타입(source_tier 아님). 합성 grounding 코퍼스 필터 = `source_license_tier IN ('licensed','crawl_ttl')`(본문 보유 소스만). DDL/시드는 [[data-model]] §3.
- **R6 — Phase 0 모멘텀 범위(LOCK):** Phase 0은 **volume+persistence만** 산출. spread·accel은 **중립 z=0**으로 동일 score 공식에 투입(컬럼·상수 불변 → Phase 1은 마이그레이션 없는 코드 토글). Phase 0 상태분류는 보수적(d1 부호+임계로 rising/cooling, **peaking은 Phase 1로 연기**, 대부분 steady).
- **R7 — BoardView.isCurrent(LOCK):** BoardView 페이로드에 `isCurrent: boolean`(= `board_view.is_current`) 포함 → 클라가 stale/last-known-good 배지 구동.
- **R8 — streamgraph 시리즈 계약(LOCK):** 최대 밴드 `STREAMGRAPH_MAX_BANDS=8`. 초과 시 서버가 단일 집계 `Other` 시리즈(`currentId="other"`, `colorKey="other-grey"`, share=나머지 서버정규화 합) 방출. Phase 0(~6 currents)은 Other 없음. ranked 리스트는 노출 전체 표시. client는 이 계약을 그대로 따름(임의 top-8 트림 금지).
- **R9 — 클라 페이로드 형태 일치(LOCK):** 클라 타입은 api-contract와 정확히 일치 — `todaysRead: { paragraph:string; asOf:string }`; `digest.movers: { climber:{currentId,name,lastRank,thisRank,note}, faller:{...} }`; BoardView에 `digestTeaser` 포함; `TimelineNode`에 `isLatest:boolean` 포함.
- **R10 — RANK_MIN_VOLUME(LOCK):** board 랭킹 포함 게이트는 별도 상수 `RANK_MIN_VOLUME=5`(흐름의 event.article_count 합 < 5면 랭킹 제외). coverage 막대 숨김 임계 `COVERAGE_MIN_N=5`와 **별개**(독립적으로 조정 가능).
- **R11 — 상태배지색 vs current hue 충돌(LOCK·헥스 확정):** current hue는 상태배지 헥스(rising amber `#F5A524`/peaking coral `#FB7A50`/cooling steel `#7C9CC0`/steady muted `#9BA3AF`)와 같을 수 없다. 이 4색은 `color_registry`에서 `is_reserved=true`로 예약, current 배정 풀에서 제외. 스펙 §3에서 충돌하는 3개(ai-governance/amber, cost-of-living/coral, middle-east/steel)는 확장 팔레트의 **구분되는 hue로 재배정**(상태배지와 ΔE 최소거리 + WCAG 비텍스트 3:1 + colorblind QA 게이트 통과 필수). **재배정 확정:** ai-governance→orchid `#C46BD8`, cost-of-living→rose `#E86A8E`, energy→lime `#9CCB3B`, middle-east→indigo `#5C6BC0`(china `#4EA8DE`/climate `#8B7FE8` 유지). 예약색에 streamgraph Other `#586170`(R8) 추가. 전체 시드는 [[data-model]] `color_registry`, 시각 확인은 `color-swatches.html`. **신규 current 배정 시에만** ΔE·WCAG 비텍스트 3:1·colorblind QA 게이트 적용.
- **R12 — 표시언어/로케일 경계(LOCK):** API는 `?lang=`(값 en|ko; Phase 0 en 전용) 또는 Accept-Language로 표시언어 수신, 응답에 `lang` 포함. 발행 뷰 테이블(`current_view`/`board_view`/`digest`)에 `lang` 컬럼을 PK에 추가(Phase 0 전 행 'en'). 한국어 = Phase 1.
- **R13 — current 상세의 watch 토글(LOCK):** `current_view`는 사용자 무관(공유 발행 객체)이라 per-user watch 상태를 **담지 않음**. 상세 화면의 "Alert me when this moves" 토글은 사용자 watch 집합을 오버레이로 표시(Phase 0 localStorage; Phase 1 `GET /v1/watch` + `PUT/DELETE /v1/watch/{currentId}`). 토글을 상세 뷰에 명시적으로 배선.
