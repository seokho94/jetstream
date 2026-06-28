# Jetstream — `phase-0-plan.md`

> **⚠️ 검수 반영(v2):** [CANON](CANON.md) **§14**로 갱신 — 충돌 시 §14 최우선. 적용: **R6**(Phase 0=volume+persistence만, spread·accel `z=0`, 보수적 분류기, peaking 연기 — momentum-engine §9/스펙 §8과 일치). 추적(Phase 1+): **R11**(색 거버넌스)·**R12**(로케일)·**R13**(watch 배선).

> **목적(한 줄):** 단일 vertical `geopolitics`에서 ~10개 수동 큐레이션 current + 8주 백필로 "current/momentum 개념이 실데이터에서 성립하는가"를 canon 상수 그대로 검증하고, 수치 게이트(§4)로 Phase 1 진입 여부를 결정한다.
>
> **적용 범위:** 본 문서는 **Phase 0** 실행 계획이다. 여기서 고정하는 스키마·식별자·상수는 전부 CANON에서 가져오며 **Phase 1/2에 상위 호환으로 승계**된다(컬럼·임계 추가만 허용, 의미 변경 금지). Phase 1(=`+technology`, 온라인 클러스터링·LLM 합성·휴먼게이트 자동화)·Phase 2(=split/merge 자동발견, 다소스·다언어)는 본 문서의 §7 "의도적 보류" 목록으로만 추적한다.

---

## 0. TL;DR — Phase 0 한 장 요약

| 항목 | Phase 0 결정값 | 근거(한 줄) |
|---|---|---|
| Vertical | `geopolitics` 1개 | 손라벨 가능한 도메인 1개로 게이트 신뢰도 확보 |
| Current 수 | 수동 큐레이션 ~10 (`current.id` 슬러그 고정) | append-only·하향식 택소노미로 ID churn=0 보장 |
| 데이터 창 | 8주 백필 + 일배치 신선화 | momentum baseline(90일 trailing median)은 백필 부족분을 short-window degrade로 처리 |
| 소스 | **GDELT 단일** (+ RSS 폴백 1개) | Phase 0는 무SLA 단일 소스 허용, §6에서 폴백 명시 |
| 임베딩 | `BGE-M3` self-host, `vector(1024)`, cosine | canon LOCK |
| 클러스터링 | 오프라인 leader-follower(일배치), `TAU_CLUSTER=0.84` | Phase 0는 배치, 온라인은 Phase 1 |
| Momentum | volume/persistence/spread/accel 전부 산출 + `score` + 4-state | canon §3 전량 구현(상태는 별도 분류기) |
| LLM 합성 | **Phase 0 비활성** — brief/timeline 수기 작성 | 게이트 변수 축소; 합성은 Phase 1 |
| 휴먼게이트 | Draft/Published 2-store 스키마만 구현, 수동 publish | 인프라 검증 목적 |
| 클라이언트 | Next.js 3뷰(board/current/digest), 순수 SVG + d3-shape | canon §8 |
| 인프라 | 단일 Postgres 16 + pgvector + (옵션)Timescale, cron+watermark | canon §6 storage note |

**무엇이 수동 / 무엇이 자동 (Phase 0 경계선)**

| 단계 | Phase 0 모드 | 비고 |
|---|---|---|
| GDELT 수집·정규화·dedup | **자동** (cron) | canonical_url + SimHash, canon §5 |
| 임베딩(title+lede) | **자동** | 정본만 임베딩 |
| current 정의/ID 배정 | **수동** | ~10개 슬러그 시드 + 룰/유사도 보조 배정 |
| article→event→current 군집 | **자동(배치) + 수동 검수** | purity 손평가 대상 |
| momentum 산출·상태분류 | **자동** | score·state 모두 자동 |
| brief / timeline 텍스트 | **수동 작성** | LLM 합성은 Phase 1 |
| coverage(region_block·outlet_type) | **자동(결정적 룩업)** | LLM 프레이밍 없음 |
| publish(Draft→Published) | **수동 트리거** | 2-store는 자동, 승인은 사람 |

---

## 1. Phase 0 목표 재정의와 범위

### 1.1 목표(재정의)
스펙 §8의 "does the concept hold up on real data?"를 **반증 가능한 수치 가설**로 재정의한다:

1. **클러스터 가설:** GDELT 실데이터에서 leader-follower(`TAU_CLUSTER=0.84`)로 묶은 event/current가 손라벨 대비 **purity ≥ 0.80**을 낸다.
2. **상태 가설:** §3 momentum 산식의 4-state 분류가 인간 판단과 **≥ 70%** 일치한다.
3. **서빙 가설:** 단일 Postgres + BFF + SVG 차트로 board p95 staleness **≤ 5분**을 활성시간에 유지한다.
4. **정성 가설:** ~10 current 데모가 "the world, zoomed out" 감각을 전달한다(편집자 10 current 검수 **< 30분/일**).

이 4개 가설이 §4 게이트를 통과하면 Phase 1로 진입한다.

### 1.2 In / Out (Phase 0)

| In scope | Out of scope (Phase 1+로 추적, §7) |
|---|---|
| `geopolitics` 단일 vertical | `technology` 등 2번째 vertical |
| GDELT 단일 소스(+RSS 폴백) | 라이선스 News API, 다소스 융합 |
| ~10 수동 current, append-only ID | 온라인 자동 군집, split/merge 자동발견 |
| 8주 백필 + 일배치 | 15분 준실시간 파이프라인 |
| momentum 전 산식 + 4-state | 상태 임계 장기 튜닝/실험 프레임워크 |
| 수기 brief/timeline | LLM 합성(name/brief/timeline/digest) |
| coverage 결정적 룩업 | LLM 프레이밍 보조 |
| board/current/digest 3뷰(읽기) | watch/alert, 개인화, 푸시 |
| 2-store 스키마 + 수동 publish | 휴먼게이트 SLA·자동 fail-closed/open 워크플로 |
| 원문 언어 직접 임베딩(영어권 위주) | 번역, 본격 다언어 |

### 1.3 명시적 비목표
- **수익화·KPI 대시보드·실험 플랫폼 없음.** Phase 0는 게이트 통과만 목표.
- **DR/백업·보안 심화 없음**(단, SSRF 가드/인젝션 가드의 **최소선**은 §6에서 구현 — 끄지 않는다).
- **AI 생성 고지 UI 없음**(Phase 0는 LLM 합성 자체가 없음).

---

## 2. 리포 스캐폴드 (§7 레이아웃 → canon 조정)

스펙 §7 트리를 canon 결정(BFF·2-store·결정적 coverage·shared types)에 맞게 조정. 루트 디렉터리 4개(`pipeline`/`api`/`web`/`shared`) 유지, 내부를 canon 산출물에 정렬.

```
jetstream/
  pipeline/                      # Python 3.12 데이터 엔진 (cron 워커)
    ingest/
      gdelt.py                   # GDELT events/mentions 풀, watermark 기반 증분
      rss.py                     # 폴백 RSS 크롤러 (SSRF 가드 경유)
      _fetch.py                  # 공용 HTTP: 화이트리스트·리다이렉트 차단(SSRF)
    normalize/
      canonical_url.py           # canonical_url 정규화(§5): host소문자·utm제거·query정렬·AMP
      simhash.py                 # 64-bit SimHash, Hamming≤3 near-dup
      dedupe.py                  # SimHash 군집화 → is_canonical 선정
      language.py                # 언어감지(원문 보존, 번역 없음)
      lede.py                    # 본문 첫 1~2문장/리드 추출(실패 시 title 단독)
      embed.py                   # BGE-M3, title+lede, vector(1024), embedding_version
    cluster/
      leader_follower.py         # 오프라인 배치 leader-follower (HNSW top-k → τ컷)
      assign.py                  # current 시드 슬러그에 append-only 배정
      lifecycle.py              # current_lifecycle_event 로깅(spawn/dormant 수동)
    momentum/
      signals.py                 # volume(7d EMA)·persistence·spread·accel_d1/d2
      normalize.py               # log1p + robust z (median/MAD), 흐름간 재표준화
      score.py                   # 0.30 z_accel+0.30 z_persist+0.25 z_vol+0.15 z_spread
      state.py                   # accel 형태 분류기 + hysteresis(2일)
    synthesis/                   # Phase 0: 스텁만(수기 입력 로더). Phase 1에서 채움
      manual_loader.py           # 수기 brief/timeline JSON → current_view 적재
    review/
      publish.py                 # Draft→Published 수동 트리거, editorial_audit 기록
    db/
      schema.sql                 # canon §6 DDL 정본 (PK/FK/파티션/인덱스)
      migrations/                # 번호순 .sql (0001_init.sql …)
      enums.sql                  # momentum_state, current_status, view_store 등
      seed_currents.sql          # ~10 geopolitics current 슬러그 + color_key
      seed_source_registry.sql   # 도메인·tier·country·region_block·license_tier
      seed_color_registry.sql    # 활성 12색 팔레트
      models.py                  # SQLAlchemy/psycopg 매핑(읽기·쓰기 헬퍼)
    jobs/
      backfill.py                # 8주 백필 오케스트레이션
      daily.py                   # 일배치 DAG: ingest→normalize→cluster→momentum→view
      watermark.py               # job별 watermark 테이블 read/write
    guards/
      cost.py                    # 비용 가드레일/킬스위치(§6)
      prompt_injection.py        # 본문 데이터채널 격리 가드(Phase 0 최소선)
  api/                           # 서빙 BFF (REST, 읽기전용 published store만)
    routes/
      board.py                   # GET /v1/board  (단일 BoardView 1콜)
      currents.py                # GET /v1/currents/{id}
      digests.py                 # GET /v1/digests/{issue}
      search.py                  # GET /v1/search?q=
    cache/etag.py                # ETag/ISR(180s) 헤더, asOf 노출
  web/                           # Next.js (App Router), 영어/웹
    app/board/page.tsx
    app/current/[id]/page.tsx
    app/digest/[issue]/page.tsx
    components/charts/
      Streamgraph.tsx            # 순수 SVG + d3-shape, share는 서버정규화값 그대로
      AttentionArc.tsx           # 1..5 마커, timeline node 공유 eventId
      SlopeChart.tsx             # digest reshuffle
      DataTableFallback.tsx      # 차트별 스크린리더용 데이터테이블 대체
    lib/momentumBadge.ts         # state→color+icon (색단독 금지: 아이콘+라벨)
  shared/
    types.ts                     # canon §6 인터페이스 미러(TS), §7 페이로드 타입
    tokens.css                   # §3 디자인 토큰 (verbatim)
    constants.ts                 # canon 상수 단일 출처(TAU_CLUSTER 등)
  infra/
    docker-compose.yml           # postgres(pgvector,timescale) 단일 인스턴스
    .env.example                 # 환경/시크릿 키 목록(값 없음)
  .github/workflows/ci.yml       # lint+typecheck+test+migrate-dryrun (최소 CI)
```

### 2.1 디렉터리 책임 매트릭스

| 디렉터리 | 책임 | 핵심 산출물 | canon 근거 |
|---|---|---|---|
| `pipeline/ingest` | GDELT/RSS 증분 수집, SSRF 가드 통과 | `article` raw 행 | §6, §12 |
| `pipeline/normalize` | URL정규화·SimHash dedup·lede·임베딩 | `canonical_url`,`simhash`,`embedding(1024)` | §1, §5 |
| `pipeline/cluster` | 배치 leader-follower, current append-only 배정 | `event`,`article_current`,`event.centroid` | §4 |
| `pipeline/momentum` | 4신호·정규화·score·state | `momentum_point` 행 | §2, §3 |
| `pipeline/synthesis` | (P0) 수기 텍스트 적재 스텁 | `current_view.brief/timeline` | §9(P1) |
| `pipeline/review` | Draft→Published 수동 publish + 감사 | `current_view`,`editorial_audit` | §11 |
| `pipeline/db` | 스키마 정본·마이그레이션·시드 | `schema.sql` | §6 |
| `pipeline/jobs` | 백필·일배치 DAG·watermark | DAG 실행, watermark 테이블 | §13(신선도) |
| `pipeline/guards` | 비용 킬스위치·인젝션 가드 | 가드 모듈 | §6, §12 |
| `api` | 뷰별 BFF, ETag/ISR/asOf | `BoardView`/`CurrentView`/`Digest` JSON | §7 |
| `web` | 3뷰 SSR, SVG 차트, 접근성 | board/current/digest 화면 | §8 |
| `shared` | 타입·토큰·상수 단일 출처 | `types.ts`,`constants.ts`,`tokens.css` | §3, §6, §7 |

---

## 3. 의존성 순서 백로그 (체크리스트 · 산출물 · 완료기준)

권장 착수 순서: **본문/임베딩/저작권 → 데이터모델 → 모멘텀 → 서빙/차트 → go/no-go**. 각 트랙은 직전 트랙의 산출물에 의존한다.

### Track A — 본문 / 임베딩 / 저작권 (수집·정규화 기반)
- [ ] **A1. SSRF 가드 + GDELT 수집기**
  - 산출물: `ingest/gdelt.py`, `guards`(화이트리스트·사설망/리다이렉트 차단), watermark 증분.
  - 완료기준: 8주 백필이 `geopolitics` 필터로 `article` raw ≥ 5,000행 적재, 모든 fetch가 `source_registry.is_whitelisted=true` 도메인만 통과.
- [ ] **A2. canonical_url 정규화 + SimHash dedup**
  - 산출물: `canonical_url.py`, `simhash.py`, `dedupe.py`.
  - 완료기준: `canonical_url` 100% 채움; 64-bit SimHash Hamming `≤ SIMHASH_HAMMING_MAX(3)` 군집화; 군집당 `is_canonical=true` 정확히 1건, 나머지 `canonical_article_id` 연결(멤버십만 보존, volume=1·spread 반영).
- [ ] **A3. 저작권/라이선스 게이트 (body TTL·license_tier)**
  - 산출물: `source_registry.license_tier`·`body_ttl` 시드, `article.purge_after` 계산.
  - 완료기준: 본문 저장은 `license_tier`가 허용하는 도메인만; `purge_after` 도래분 일배치 purge 동작 검증. 본문 미허용 소스는 `body=NULL`, `body_extracted=false`로 메타만 보존.
- [ ] **A4. lede 추출 + BGE-M3 임베딩**
  - 산출물: `lede.py`, `embed.py`.
  - 완료기준: 대상 텍스트 = **title + lede**(추출 실패 시 title 단독); 정본만 `embedding vector(1024)` 채움, 그 외 NULL; `embedding_version="bge-m3@v1.5"` 전건 기록; HNSW(`m=16, ef_construction=64`) 인덱스 생성.

### Track B — 데이터모델 (스키마 정본·시드)
- [ ] **B1. 스키마 + ENUM + 파티셔닝**
  - 산출물: `db/schema.sql`, `enums.sql`.
  - 완료기준: canon §6 전 테이블 DDL 적용. `article` PK `(id, published_at)` 월 RANGE 파티션; `momentum_point` PK `(current_id, t)`; `article_current` PK `(current_id, article_id)`; ENUM `momentum_state{rising,peaking,cooling,steady}` 등 생성. 마이그레이션 dry-run CI 통과.
- [ ] **B2. 레지스트리 시드 (current/source/color)**
  - 산출물: `seed_currents.sql`(~10 슬러그+`taxonomy_seed`+`coverage_config`), `seed_source_registry.sql`, `seed_color_registry.sql`.
  - 완료기준: ~10 `current` 슬러그 ID 고정·`color_key` 모두 `color_registry` FK 해소; current당 hue 동결(append-only), 모멘텀 의미색(up `#6FBF73`/down `#D08585`) 충돌 hue 제외.
- [ ] **B3. 군집 배정 (배치 leader-follower)**
  - 산출물: `leader_follower.py`, `assign.py`, `lifecycle.py`.
  - 완료기준: HNSW top-k(`CLUSTER_TOPK=20`)→cosine `τ=TAU_CLUSTER(0.84)` 컷으로 event 형성, centroid EMA(`CENTROID_ALPHA=0.2`), 14일 윈도 만료(`event.expires_at=last_seen+14d`); event→current는 **append-only 배정**(주간 재군집 금지); `current_lifecycle_event(type=spawn)` 시드 기록.

### Track C — 모멘텀 (신호·정규화·점수·상태)
- [ ] **C1. 4신호 산출**
  - 산출물: `signals.py`.
  - 완료기준: `volume`=정본수 7일 EMA; `persistence_days`=robust baseline 초과 연속일(`PERSIST_GAP_TOL=2`); `spread`=신디케이션 접은 후 outlet/country 다양성(`spread_outlets`,`spread_countries` 별도 보존); `accel_d1`(7d 1차), `accel_d2`(14d 2차).
- [ ] **C2. 정규화 + score**
  - 산출물: `normalize.py`, `score.py`.
  - 완료기준: 흐름내 `log1p(volume)` + robust z `z=(x-median)/(1.4826*MAD)`, baseline=60~90일(default 90) trailing; `score = 0.30*z_accel + 0.30*z_persist + 0.25*z_vol + 0.15*z_spread`; board/weekly_rank는 score 내림차순.
- [ ] **C3. 상태 분류기(랭킹과 분리)**
  - 산출물: `state.py`.
  - 완료기준: 상태는 **accel 형태 분류기**로 산출(score와 분리). `tau_state=k*MAD`(`STATE_K=1.0`), hysteresis 진입 `tau_enter`/이탈 `tau_exit=0.7*tau_enter`, 전환 2일 연속 충족 확정(`STATE_HYSTERESIS_DAYS=2`). 매핑: rising(d1>0,d2≥0)/peaking(d1≈0,d2<0)/cooling(d1<0)/steady(트리거 없음). 결과를 `momentum_point.state` 적재.
- [ ] **C4. weekly_rank 동결**
  - 산출물: 주간 랭크 캡처 job.
  - 완료기준: `weekly_rank(issue,current_id)` = `week_of,rank,score,state,captured_at`, 캡처 후 **불변**(reshuffle 근거).

### Track D — 서빙 / 차트 (BFF·SVG·접근성)
- [ ] **D1. 발행 객체 생성 (board/current/digest)**
  - 산출물: `board_view`,`current_view`(Draft/Published),`digest` 생성기 + 수기 brief/timeline 로더.
  - 완료기준: `board_view.streamgraph`의 **share를 서버에서 정규화**(클라 비계산); `current_view.coverage`는 결정적 룩업 산출; arc[].marker(1..5)=timeline[].node(1..5) `eventId` 공유 검증.
- [ ] **D2. REST BFF**
  - 산출물: `GET /v1/board`,`/v1/currents/{id}`,`/v1/digests/{issue}`,`/v1/search?q=`.
  - 완료기준: `/v1/board` 단일 `BoardView` 1콜; ETag + ISR(`ISR_REVALIDATE=180s`); 응답에 `asOf` 신선도 노출; 클라 폴링 `POLL_INTERVAL=60s`.
- [ ] **D3. 3뷰 + SVG 차트 + 접근성**
  - 산출물: board/current/digest 페이지, `Streamgraph`/`AttentionArc`/`SlopeChart`/`DataTableFallback`.
  - 완료기준: **순수 SVG + d3-shape**(호버 의존 금지, 탭타깃 ≥44px); state는 색단독 금지(아이콘+라벨); 다크 WCAG 비텍스트 대비 3:1; 차트마다 데이터테이블 대체 제공.
- [ ] **D4. 2-store publish + 감사**
  - 산출물: `publish.py`.
  - 완료기준: Draft→Published 수동 트리거, `current_view.is_last_known_good` 노출; 모든 변이 `editorial_audit` append-only 기록.

### Track E — go/no-go (게이트 측정)
- [ ] **E1. 손라벨 + purity 측정** — 산출물: 라벨셋·purity 스크립트. 완료기준: 샘플 purity 산출, **≥ 0.80** 판정.
- [ ] **E2. 상태-인간판단 일치** — 완료기준: current-week 샘플 합의도 **≥ 70%**.
- [ ] **E3. coverage 결정적 룩업 비율** — 완료기준: **≥ 95%**.
- [ ] **E4. 신선도 SLO** — 완료기준: board p95 staleness **≤ 5분**(활성시간), 편집자 검수 **< 30분/일**.
- [ ] **E5. go/no-go 회의** — 완료기준: §4 표 전 항목 pass/fail 기록 → Phase 1 진입 결정.

---

## 4. Go / No-Go 지표 (Phase 1 진입 게이트)

canon §13 그대로. 각 지표는 측정 방법과 함께 고정한다.

| # | 지표 | 임계(게이트) | 측정 방법 | 미달 시 |
|---|---|---|---|---|
| G1 | 클러스터 purity | **≥ 0.80** | 손라벨 샘플(이벤트 N≥200) 대비 majority-class 비율 | `TAU_CLUSTER` 0.82~0.86 범위 재튜닝 후 재측정 |
| G2 | current ID churn | **= 0** | append-only 구조 불변 검증(주간 재군집 금지) | 구조 위반이면 즉시 차단 |
| G3 | 상태-인간판단 일치 | **≥ 70%** | current-week 샘플, 분류기 state vs 편집자 라벨 | `STATE_K`/hysteresis 재조정 |
| G4 | coverage 결정적 룩업 비율 | **≥ 95%** | `region_block`+`outlet_type` 룩업 성공 / 전체 막대 | `source_registry` 메타 보강 |
| G5 | 인용 유효성 | **100%** | (P0: 수기 timeline의 모든 source URL 해소) | 미해소 인용 발행 차단 |
| G6 | verifier 환각 플래그 | **< 5%** | (P0: LLM 미사용 → N/A, Phase 1 게이트로 승계) | Phase 1 적용 |
| G7 | board p95 staleness | **≤ 5분** (활성시간) | `asOf` vs 요청시각 분포 p95 | ISR/배치 주기 단축 |
| G8 | 편집자 검수 시간 | **< 30분/일** (10 current) | 검수 타임박스 측정 | UI/큐 단순화 |

> **게이트 판정:** G1·G3·G4·G7·G8 **전부 pass + G2=0 + G5=100%** → Phase 1 진입. G6은 Phase 0에서 N/A(LLM 미사용)지만 Phase 1 게이트로 그대로 승계한다.

**정성 신호(보조, 게이트 아님):** 데모 시청자가 ~10 current에서 "지금 세계가 어디로 가는지" 20초 내 파악 / 적어도 1개 current의 state 전환을 "스파이크 아닌 누적"으로 올바르게 해석.

---

## 5. 최소 인프라

### 5.1 단일 데이터스토어
- **Postgres 16 단일 인스턴스** + **pgvector**(HNSW `m=16, ef_construction=64`, 질의 `ef_search=100`, `vector_cosine_ops`).
- **TimescaleDB = 옵션.** Phase 0는 `momentum_point`를 평범한 시간버킷 테이블로 운용; 행수가 작아 하이퍼테이블 불필요. 단, `momentum_point`를 **Timescale 하이퍼테이블 호환 스키마**(PK `(current_id, t)`)로 만들어 Phase 1에서 무중단 전환 가능하게 둔다. 트레이드오프: Timescale 선도입은 운영 복잡도↑·이득 미미 → 보류.
- 발행 객체(`board_view`/`current_view`/`digest`)는 같은 DB의 읽기최적 테이블에 둔다(스펙 §6 storage note). 캐시 분리는 Phase 2.

### 5.2 오케스트레이션 — cron + watermark
- **cron** 기반 일배치 DAG(`jobs/daily.py`): `ingest → normalize(dedupe→lede→embed) → cluster → momentum → view-build`. 큐/워크플로 엔진은 Phase 1로 보류(트레이드오프: Airflow 등은 Phase 0 규모에 과투자).
- **watermark 테이블**로 증분 처리: `job_watermark(job_name PK, last_processed_at, last_run_at, status)`. 각 단계는 watermark 이후만 처리 → 재실행 안전(idempotent upsert).
- 백필은 `jobs/backfill.py`가 8주 구간을 일자 청크로 순차 실행 후 watermark를 현재로 전진.

### 5.3 환경 / 시크릿 / CI 최소선

| 환경변수 | 용도 | 비고 |
|---|---|---|
| `DATABASE_URL` | Postgres 접속 | `.env`(로컬), GH Secrets(CI) |
| `EMBED_MODEL=bge-m3`, `EMBED_REVISION=v1.5` | 임베딩 고정 | canon LOCK |
| `GDELT_BASE_URL` | 수집 엔드포인트 | 폴백 전환에 사용 |
| `INGEST_ALLOWLIST` | SSRF 화이트리스트 도메인 | 쉼표구분 |
| `COST_KILLSWITCH=off` | 비용 킬스위치 | §6 |
| `ANTHROPIC_API_KEY` | (P1 예약) | Phase 0 미사용 |

- **시크릿:** `.env`는 git-ignore, `infra/.env.example`에 키 목록만(값 없음). CI는 GitHub Actions Secrets.
- **CI 최소선(`ci.yml`):** ① Python lint(ruff)+typecheck(mypy) ② web typecheck(tsc)+lint ③ unit test(dedupe/simhash/score/state 골든테스트) ④ **migration dry-run**(schema.sql을 임시 Postgres에 적용). 배포 자동화·E2E는 Phase 1.
- **로컬:** `infra/docker-compose.yml` 단일 Postgres(pgvector+timescale 확장 포함 이미지) → `make up && make migrate && make seed`.

---

## 6. 리스크와 완화

| 리스크 | 영향 | 완화(Phase 0 구체) |
|---|---|---|
| **GDELT 무SLA·단일 장애점** | 수집 중단 시 신선도 SLO(G7) 붕괴 | (1) 폴백 RSS 크롤러 1개를 SSRF 가드 경유로 상시 준비, GDELT 연속 N회 실패 시 자동 전환. (2) 일배치는 watermark 기반이라 복구 후 자동 따라잡기. (3) board는 `is_last_known_good` 서빙으로 빈 화면 방지. (4) `asOf` 노출로 신선도 투명화. |
| **본문 라이선스/저작권** | 비허용 본문 저장 시 법적 리스크 | `source_registry.license_tier`로 본문 저장 게이트; 미허용은 `body=NULL`·메타만; `body_ttl`→`article.purge_after` 도래분 일배치 purge. LLM 합성 미사용(P0)이라 본문 노출면 최소. |
| **임베딩/추론 비용 폭주** | 백필 재처리 시 비용·시간 폭증 | `guards/cost.py` 가드레일: 일일 임베딩 토큰·요청 상한, 초과 시 `COST_KILLSWITCH=on`으로 배치 중단(부분 진행분 watermark 보존). BGE-M3 self-host로 단가 통제. |
| **프롬프트 인젝션(본문→LLM)** | (P1 위험이나 가드 골격은 P0) | 본문은 **데이터 채널로만** 전달하는 가드 모듈(`guards/prompt_injection.py`) 골격 구현, 명령 무시 가드·인용 스팬 검증 훅 예약. P0는 LLM 미사용으로 노출 0. |
| **SSRF(크롤링)** | 사설망/메타데이터 접근 | 화이트리스트 도메인만, IP 리터럴·리다이렉트·사설망 대역 차단(`_fetch.py`). 끄지 않는 최소선. |
| **백필 부족으로 baseline 불안정** | 90일 trailing median 미충족 | baseline 가용일수 부족 시 short-window degrade(가용 구간 median/MAD 사용)로 운용, 데이터 누적되며 자동 정상화. score는 산출하되 신뢰구간 낮음을 게이트 해석에 반영. |
| **purity 게이트 미달(G1)** | Phase 1 진입 지연 | `TAU_CLUSTER` 0.82~0.86 범위 내 재튜닝, 손라벨 셋 확대 후 재측정. 구조(append-only)는 불변 유지. |

---

## 7. 의도적으로 Phase 1+로 미루되 추적할 항목

| 항목 | 보류 사유(트레이드오프) | 추적 트리거(언제 다룬다) |
|---|---|---|
| **보안 심화**(에디터 authn/authz 필드별 권한, 전 변이 감사 워크플로) | P0는 단일 운영자·수동 publish | Phase 1 휴먼게이트 자동화 시 §11/§12 전량 |
| **KPI / 실험 프레임워크**(A/B, retention) | P0 목표는 게이트, 제품지표 아님 | Phase 1 MVP 출시 직후 |
| **DR / 백업**(PITR, 다중 리전) | 단일 인스턴스로 충분, 데이터 재생성 가능 | Phase 1 사용자 데이터(watch) 등장 시 |
| **AI 생성 고지 UI** | P0는 LLM 합성 미사용 | Phase 1 LLM brief/timeline 도입과 동시 |
| **수익화**(구독·B2B 엔진) | 조기 과투자 방지 | Phase 2 |
| **에디터 인력/SLA**(롤백·긴급 unpublish 운영) | P0 검수 <30분/일, 1인 운영 | Phase 1 휴먼게이트 SLA 정의 시 §11 |
| **온라인 클러스터링·split/merge 자동발견** | P0는 배치·append-only로 충분 | Phase 1(온라인)/Phase 2(Jaccard-Hungarian) |
| **LLM 합성·Citations·verifier** | 게이트 변수 축소 | Phase 1 §9 전량(prompt caching·char span 바인딩) |
| **다언어/번역·다소스 융합** | P0 영어권 GDELT로 충분 | Phase 2 §5 확장 |

> 추적 방식: 위 항목은 backlog에 `phase-1` / `phase-2` 라벨로 등록만 하고 Phase 0 범위에서 제외한다. canon 컬럼(예: `current_view.reviewed_by`, `editorial_audit`)은 **스키마에 이미 존재**하므로 Phase 1 활성화가 무중단이다.

---

## 8. 마일스톤 / 대략 순서

8주 백필 데이터를 기준으로, 구현은 트랙 의존순(A→B→C→D→E)으로 진행. 대략 6 마일스톤.

| 마일스톤 | 내용 | 주요 트랙 | 종료 산출물 |
|---|---|---|---|
| **M0 — 스캐폴드** | 리포 4트리, docker-compose 단일 Postgres, CI 최소선, `shared/constants.ts`·`tokens.css` verbatim | (인프라) | `make up/migrate/seed` 동작 |
| **M1 — 수집·정규화·임베딩** | SSRF 가드·GDELT 수집·canonical_url·SimHash dedup·lede·BGE-M3 임베딩, 라이선스 게이트 | A1~A4 | 8주 백필 적재 + 정본 임베딩 |
| **M2 — 데이터모델·군집** | schema.sql 정본·시드(current/source/color)·배치 leader-follower append-only 배정 | B1~B3 | event/current 군집 + ID 고정 |
| **M3 — 모멘텀** | 4신호·정규화·score·4-state 분류기·weekly_rank 동결 | C1~C4 | `momentum_point` 일자 채움 |
| **M4 — 서빙·차트** | board_view share 서버정규화·BFF 4엔드포인트·3뷰 SVG·데이터테이블 대체·2-store publish·수기 brief/timeline | D1~D4 | 3뷰 데모 동작(asOf/ETag/ISR) |
| **M5 — go/no-go** | 손라벨 purity·상태합의·coverage비율·신선도/검수 측정 → 게이트 판정 | E1~E5 | §4 표 채움 + Phase 1 결정 |

**순서 원칙:** D(서빙)는 C(모멘텀) 산출물에, C는 B(군집)에, B는 A(임베딩)에 의존 — 역류 금지. LLM 합성·온라인 군집·휴먼게이트 자동화는 마일스톤에서 제외(§7).
