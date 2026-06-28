# Meridian — API Contract (`api-contract.md`)

> **⚠️ 검수 반영(v2):** [CANON](CANON.md) **§14**로 갱신 — 충돌 시 §14 최우선. 적용: **R2**(arc 평탄 `ArcPoint[]`) · **R3**(board rank=live momentum score 기반) · **R4**(`ArcPoint.value`=정규화 0..1) · **R7**(`BoardView.isCurrent` 추가) · **R8**(streamgraph 최대 8밴드+`Other` 시리즈) · **R12**(`lang` 파라미터·응답 필드) · **R13**(watch=Phase 1; `CurrentView`는 watch 상태 미포함, 클라 오버레이).

> **목적 (한 줄):** Meridian의 세 뷰(board / current / digest)와 search를 서빙하는 **읽기전용 REST + 뷰별 BFF** API의 경로·페이로드·신선도·에러 계약을 canon 데이터모델과 1:1로 고정한다.
>
> **적용 범위**
> - **Phase 0 (구속):** `GET /v1/board`, `GET /v1/currents/{id}`, `GET /v1/digests/{issue}`, `GET /v1/search?q=` — vertical 1개(`geopolitics`), 수동 큐레이션 current ~10개, 8주 백필. 본 문서 전체가 발효.
> - **Phase 1:** vertical 2개(+`technology`), watch/alert 엔드포인트(`/v1/watch*`) 활성, 온라인 클러스터링·LLM 합성·휴먼게이트 자동화. 본 계약 동일 적용.
> - **Phase 2:** split/merge 자동 발견. 본 계약은 **상위 호환만 허용**(필드·쿼리파라미터 추가 가능, 기존 의미·코드·경로 변경 금지).
>
> 충돌 시 **canon이 이긴다.** 본 문서의 모든 상수(`ISR_REVALIDATE`, `POLL_INTERVAL` 등)·식별자·엔드포인트는 canon §6/§7에서 그대로 가져온 것이며 재발명하지 않는다.

---

## 1. 설계 원칙 — 근거

| 결정 | 값 | 근거 (한 줄 트레이드오프) | canon |
|---|---|---|---|
| 스타일 | **REST + 뷰별 BFF** (GraphQL 불채택) | 표면이 3뷰로 고정·읽기전용이라 GraphQL의 동적 쿼리 유연성이 불필요하고, BFF가 서버에서 정규화·denorm을 끝내 클라 계산/오버페치를 제거 → HTTP 캐시·ETag·CDN과 자연 정합. | §7 |
| 버전 prefix | **`/v1`** | 경로 버전은 CDN/캐시키·라우팅에 단순. 헤더 협상보다 운영 비용이 낮음. | §7 |
| 모드 | **읽기전용 (GET only)** | 클라는 **published store만** 읽는다(canon §6 `board_view.is_current`, `current_view(store='published')`, `digest`). 파이프라인·에디터 변이는 별도 internal 평면(본 계약 밖). 단 watch(Phase 1)만 사용자 상태 변이로 예외(§2.5). | §6, §7, §11 |
| 뷰별 BFF | `/v1/board`는 **단일 `BoardView` 1콜** | 라운드트립 1회로 board 전체(streamgraph+ranked+todaysRead+digestTeaser) 서빙 → p95 staleness ≤ 5분 목표(§13)와 모바일 첫 페인트에 유리. 단점: 응답이 크다 → ETag/304로 상쇄. | §7, §13 |
| share 정규화 위치 | **서버** (클라 비계산) | streamgraph share는 `board_view.streamgraph`에 **서버 정규화 완료분만** 실음 → 클라/SSR 간 수치 불일치 제거, 접근성 데이터테이블 대체(§8)와 동일 소스. | §7, §8 |
| board ranking 산출 | **라이브** (매 `as_of` `momentum_point.score`로 재계산) | board는 모멘텀-우선의 **상태(state) 뷰**라 일중에도 신선해야 한다. `RankedRow.rank`는 매 `as_of`에 `RANK() OVER (ORDER BY score DESC)`로 서버에서 재계산(momentum-engine §5.1/§5.2). 주간 동결값(`weekly_rank`)은 board가 아니라 **digest.reshuffle 전용**. 트레이드오프: 일중 순위가 흔들릴 수 있으나 `POLL_INTERVAL=60s` 폴링·`asOf` 노출로 "지금 기준"임을 명시. | §3, §7 |

읽기전용·BFF·서버정규화 원칙은 모두 "클라는 **서버가 끝낸 값**을 그대로 렌더만 한다(클라 비계산)"는 canon의 일관 자세에서 파생한다. 다만 **신선도 차원은 뷰별로 다르다**: board의 ranked/state는 매 `as_of` **라이브 산출**(momentum-engine §5.1), digest의 reshuffle/movers는 주 1회 **동결**(`weekly_rank` 캡처, canon §6)이다. 즉 board는 "지금의 모멘텀"을, digest는 "주간에 보여진 사실(frozen)"을 렌더한다 — 둘을 혼동하지 않도록 source를 분리한다(board=`momentum_point`, digest=`weekly_rank`).

---

## 2. 엔드포인트 표면

공통: 모든 응답은 `Content-Type: application/json; charset=utf-8`, `ETag`(canon의 `*.etag` 컬럼 값), `Cache-Control`(§4) 동반. 모든 4xx/5xx는 §5의 공통 error envelope를 따른다.

### 2.1 `GET /v1/board` — 보드(상태)

- **경로 파라미터:** 없음.
- **쿼리 파라미터:**
  - `vertical` (string, optional, default `geopolitics`) — Phase 0은 `geopolitics` 고정, Phase 1부터 `technology` 허용. 미허용 값 → `400 invalid_param`.
- **동작:** `board_view` 중 `is_current = true` 1행을 `BoardView` JSON으로 반환(§3.1). `ranked`는 해당 `as_of`의 `momentum_point.score`로 서버 라이브 랭킹된 결과, streamgraph share는 서버 정규화 완료분.
- **응답 코드:**
  | code | 조건 |
  |---|---|
  | `200` | 현행 board 반환. `ETag`, `Cache-Control: public, max-age=60, stale-while-revalidate=120` |
  | `304` | `If-None-Match`가 현행 `etag`와 일치 — 본문 없음 |
  | `400` | `vertical` 미허용 (`invalid_param`) |
  | `503` | 현행 board 없음/발행 중단 — last-known-good 없을 때 (`no_current_board`), `Retry-After: 60` |

### 2.2 `GET /v1/currents/{id}` — 커런트(이해)

- **경로 파라미터:** `id` (string, **current 슬러그**, canon `current.id`, 예 `ai-governance`).
- **쿼리 파라미터:**
  - `as_of` (ISO-8601, optional) — 과거 published 스냅샷 요청. 미지정 시 최신 published. Phase 0은 최신만 보장; 미지원 시점 → `200` + 최신 + `Warning` 헤더(다운그레이드).
- **동작:** `current_view`에서 `(current_id=id, store='published')` 중 최신(또는 `is_last_known_good=true`) 1행을 `CurrentView`로 반환(§3.2).
- **응답 코드:**
  | code | 조건 |
  |---|---|
  | `200` | 정상. `ETag = current_view.etag` |
  | `301` | `current.status = 'merged'` → `Location: /v1/currents/{merged_into}` (영구 리다이렉트, §6) |
  | `304` | `If-None-Match` 일치 |
  | `404` | 존재하지 않는 슬러그 (`current_not_found`) |
  | `410` | `current.status = 'dormant'` 이고 후속 current 없음 — 본문에 `lastKnownGood` 메타(§6) |
  | `503` | published store 비어있고 last-known-good도 없음 (high-risk fail-closed, §11) |

### 2.3 `GET /v1/digests/{issue}` — 다이제스트(변화)

- **경로 파라미터:** `issue` (integer ≥ 1, canon `digest.issue` PK).
- **쿼리 파라미터:** 없음. (특수값 `latest`는 별칭으로 허용 → 최신 발행 issue로 `302`.)
- **동작:** `digest`에서 `issue` 1행을 반환(§3.3). store는 `published`만.
- **응답 코드:**
  | code | 조건 |
  |---|---|
  | `200` | 정상. `ETag = digest.etag`, `Cache-Control: public, max-age=300, immutable`(과거 issue), 최신 issue는 `max-age=60` |
  | `302` | `issue=latest` → `Location: /v1/digests/{n}` |
  | `304` | `If-None-Match` 일치 |
  | `400` | `issue` 비정수/≤0 (`invalid_param`) |
  | `404` | 미발행/미존재 issue (`digest_not_found`) |

### 2.4 `GET /v1/search?q=` — 검색

- **경로 파라미터:** 없음.
- **쿼리 파라미터:**
  - `q` (string, **required**, 1~256자) — 질의. 누락/공백 → `400 missing_q`.
  - `vertical` (optional, default 전체) — 결과 필터.
  - `type` (optional, enum `current|event|article`, 반복 허용, default `current,event`) — 인덱스 대상(§7).
  - `limit` (int, 1~50, default 20), `cursor` (opaque, §5 페이지네이션).
- **동작:** 시맨틱(pgvector HNSW, BGE-M3 1024d, cosine) + 전문검색 하이브리드(§7). 결과는 `current` 중심, 매칭 `event`/`article`는 근거로 동반.
- **응답 코드:**
  | code | 조건 |
  |---|---|
  | `200` | 결과(빈 배열 포함). `Cache-Control: private, max-age=30` |
  | `400` | `q` 누락 또는 길이 초과 (`missing_q` / `invalid_param`) |
  | `422` | `type`/`vertical` 미허용 enum (`unprocessable_param`) |
  | `429` | 레이트리밋 초과 (§5), `Retry-After` 동반 |

### 2.5 Watch / Alert — **Phase 1** (canon §0, spec §8 "Watch/alerts")

> Phase 0에서는 미노출(라우트 자체가 `404`). Phase 1에서 활성. 사용자 상태를 다루므로 본 API의 **유일한 비-GET 평면**이며 별도 authn(세션/토큰) 필요.

- `GET /v1/watch` — 현재 사용자가 watch 중인 current 목록. `200` / `401 unauthorized`.
- `PUT /v1/watch/{currentId}` — "Alert me when this moves" 토글 ON(멱등). `200`(상태 반영) / `401` / `404 current_not_found` / `409`(merged→`Location` 안내).
- `DELETE /v1/watch/{currentId}` — 토글 OFF(멱등). `204` / `401`.
- 알림 트리거 의미: 대상 current의 `momentum_point.state` 전환이 **2일 연속 확정**(`STATE_HYSTERESIS_DAYS=2`)된 시점(canon §3). 즉 "moves" = 상태 확정 전환이며 일별 흔들림이 아니다.

---

## 3. 페이로드 스키마 + 예시 (canon 데이터모델 1:1 매핑)

표기: TS 인터페이스로 스키마를, 그 아래 실제 JSON 예시를 둔다. 모든 필드 옆 주석은 **출처 canon 컬럼**이다. 날짜는 ISO-8601 UTC.

### 3.1 `BoardView` — `GET /v1/board` (canon `board_view`)

```ts
interface BoardView {
  asOf: string;            // board_view.as_of  — 데이터 신선도 기준시각(§4)
  generatedAt: string;     // board_view.generated_at — 객체 생성시각
  vertical: string;        // vertical.id ("geopolitics")
  todaysRead: TodaysRead;  // board_view.todays_read
  streamgraph: Streamgraph;// board_view.streamgraph (서버 정규화 share)
  ranked: RankedRow[];     // board_view.ranked
  digestTeaser: DigestTeaser;
  stats: BoardStats;       // board_view.stats
  etag: string;            // board_view.etag (= 응답 ETag 헤더)
}

interface TodaysRead {     // board_view.todays_read jsonb
  paragraph: string;       // 한 문단 브리핑
  asOf: string;
}

interface Streamgraph {    // board_view.streamgraph jsonb — share는 서버 정규화
  weeks: string[];         // ~8주 버킷(주 시작일 ISO). Phase 0 = 8
  shareDenominator: "sum_volume_per_week"; // §아래 '정규화 규칙' 참조 (불변)
  series: StreamSeries[];
  altTable: StreamAltCell[]; // §8 스크린리더용 데이터테이블 대체
}
interface StreamSeries {
  currentId: string;       // current.id
  name: string;            // current.name
  colorKey: string;        // current.color_key → color_registry.color_key
  hex: string;             // color_registry.hex (서버 해석, 클라 룩업 제거)
  // share[i] = 해당 주 정규화 점유율, 0..1, Σ_currents share[i] == 1
  share: number[];         // weeks와 동일 길이
}
interface StreamAltCell { week: string; currentId: string; share: number; }

interface RankedRow {      // board_view.ranked[] — momentum_point 라이브 투영(매 as_of 재계산)
  rank: number;            // 라이브 랭크: 매 as_of RANK() OVER (ORDER BY momentum_point.score DESC) (momentum-engine §5.1/§5.2). weekly_rank 아님(동결값은 digest.reshuffle 전용)
  currentId: string;       // current.id
  name: string;            // current.name
  colorKey: string;        // current.color_key
  hex: string;             // color_registry.hex
  state: MomentumState;    // momentum_point.state (4상태)
  badge: StateBadge;       // 아이콘+라벨+색 (색 단독 인코딩 금지 §2/§8)
  score: number;           // momentum_point.score (가중합, §3 산식) — rank의 정렬 키
  sparkline: number[];     // 최근 attention(정규화 volume) 표시용
  attention: number;       // 막대 길이용(0..1, 서버 정규화)
}

type MomentumState = "rising" | "peaking" | "cooling" | "steady"; // canon §2
interface StateBadge {     // canon §2 색·아이콘 고정
  label: MomentumState;
  icon: "ti-trending-up"|"ti-activity"|"ti-trending-down"|"ti-minus";
  hex:  "#F5A524"|"#FB7A50"|"#7C9CC0"|"#9BA3AF";
}

interface DigestTeaser {
  issue: number;           // digest.issue
  lede: string;            // digest.lede (티저 노출분)
  weekOf: string;          // digest.week_of
  href: string;            // "/v1/digests/{issue}"
}
interface BoardStats {     // board_view.stats jsonb
  currentsTracked: number;
  newThreads: number;
  storiesScanned: number;
}
```

**board ranked 랭킹 규칙 (서버 라이브 산출, 클라 비계산):**
- `RankedRow.rank`는 **매 `as_of`에 재계산되는 라이브 순위**다. 서버가 해당 `as_of`의 `momentum_point` 행에서 `score`(canon §3 가중합 `0.30*z_accel + 0.30*z_persist + 0.25*z_vol + 0.15*z_spread`) 내림차순으로 `RANK() OVER (ORDER BY score DESC)`를 부여한다(momentum-engine §5.1/§5.2). 따라서 board는 일중 폴링(`POLL_INTERVAL=60s`)으로 새 `board_view`가 발행되면 순위가 바뀔 수 있다 — 이는 board가 "지금의 모멘텀"을 보여주는 **상태 뷰**(spec §1)임의 직접 귀결이다.
- **랭킹점수 ≠ 상태신호**(canon §3): `rank`/`score`는 모멘텀 가중합, `state`/`badge`는 accel 형태 분류기 산출로 서로 독립이다. 같은 `RankedRow` 안에 공존하나 다른 산출 경로다.
- **주간 동결값(`weekly_rank.rank`)은 board에 쓰지 않는다.** `weekly_rank`(canon §6 '보여진 사실'·불변)는 **digest의 reshuffle/movers 전용**(§3.3)이다. board의 일중 라이브 순위와 digest의 주간 동결 순위는 서로 다른 source이며 값이 달라도 정상이다(예: 화요일 board에서 1위지만 지난 주 동결 `weekly_rank`는 3위).

**streamgraph share 정규화 규칙 (서버 고정, 클라 비계산):**
- **분모 = 해당 주의 모든 노출 current `volume` 합** (`volume` = 일별 정본 기사수의 **7일 EMA**, canon §3). 즉 주 `i`에 대해 `share[c][i] = volume[c][i] / Σ_c volume[c][i]`.
- 따라서 각 주에서 **Σ_currents share == 1.0** (부동소수 허용오차 ±1e-6). `shareDenominator` 필드는 이 규칙을 `"sum_volume_per_week"`로 명시·고정.
- streamgraph에 싣는 current 집합 = board에 노출되는 ranked 집합(Phase 0 ~6, spec §2.1 "6 currents"). 분모도 이 집합 한정 → "전체 세계 대비"가 아니라 "노출 current 간 점유"임을 클라가 가정하지 않도록 서버가 못박는다.

**예시 응답 (`200`):**
```json
{
  "asOf": "2026-06-28T06:00:00Z",
  "generatedAt": "2026-06-28T06:02:11Z",
  "vertical": "geopolitics",
  "todaysRead": {
    "paragraph": "AI governance가 4주째 꾸준히 누적되며 보드 1위로 올라섰고, 중동은 감속 국면에 들어섰습니다. 극적 사건 없이 축적된 흐름입니다.",
    "asOf": "2026-06-28T06:00:00Z"
  },
  "streamgraph": {
    "weeks": ["2026-05-04","2026-05-11","2026-05-18","2026-05-25","2026-06-01","2026-06-08","2026-06-15","2026-06-22"],
    "shareDenominator": "sum_volume_per_week",
    "series": [
      { "currentId": "ai-governance", "name": "AI governance", "colorKey": "ai-governance", "hex": "#F5A524",
        "share": [0.14,0.15,0.17,0.19,0.22,0.24,0.27,0.30] },
      { "currentId": "cost-of-living", "name": "Cost of living", "colorKey": "cost-of-living", "hex": "#FB7A50",
        "share": [0.24,0.23,0.22,0.21,0.20,0.19,0.18,0.17] },
      { "currentId": "energy", "name": "Energy", "colorKey": "energy", "hex": "#34D0BA",
        "share": [0.16,0.16,0.17,0.17,0.18,0.18,0.18,0.19] },
      { "currentId": "climate", "name": "Climate", "colorKey": "climate", "hex": "#8B7FE8",
        "share": [0.12,0.12,0.12,0.13,0.13,0.14,0.14,0.14] },
      { "currentId": "middle-east", "name": "Middle East", "colorKey": "middle-east", "hex": "#7C9CC0",
        "share": [0.20,0.20,0.19,0.18,0.16,0.14,0.12,0.11] },
      { "currentId": "china", "name": "China", "colorKey": "china", "hex": "#4EA8DE",
        "share": [0.14,0.14,0.11,0.12,0.11,0.11,0.11,0.09] }
    ],
    "altTable": [
      { "week": "2026-06-22", "currentId": "ai-governance", "share": 0.30 },
      { "week": "2026-06-22", "currentId": "cost-of-living", "share": 0.17 }
    ]
  },
  "ranked": [
    { "rank": 1, "currentId": "ai-governance", "name": "AI governance", "colorKey": "ai-governance", "hex": "#F5A524",
      "state": "rising",  "badge": { "label": "rising",  "icon": "ti-trending-up",   "hex": "#F5A524" },
      "score": 1.42, "sparkline": [0.14,0.17,0.22,0.27,0.30], "attention": 0.30 },
    { "rank": 2, "currentId": "cost-of-living", "name": "Cost of living", "colorKey": "cost-of-living", "hex": "#FB7A50",
      "state": "peaking", "badge": { "label": "peaking", "icon": "ti-activity",      "hex": "#FB7A50" },
      "score": 1.05, "sparkline": [0.24,0.22,0.20,0.18,0.17], "attention": 0.17 },
    { "rank": 5, "currentId": "middle-east", "name": "Middle East", "colorKey": "middle-east", "hex": "#7C9CC0",
      "state": "cooling", "badge": { "label": "cooling", "icon": "ti-trending-down", "hex": "#7C9CC0" },
      "score": 0.31, "sparkline": [0.20,0.18,0.16,0.13,0.11], "attention": 0.11 },
    { "rank": 6, "currentId": "china", "name": "China", "colorKey": "china", "hex": "#4EA8DE",
      "state": "steady",  "badge": { "label": "steady",  "icon": "ti-minus",         "hex": "#9BA3AF" },
      "score": 0.08, "sparkline": [0.14,0.11,0.12,0.11,0.09], "attention": 0.09 }
  ],
  "digestTeaser": {
    "issue": 34, "weekOf": "2026-06-22",
    "lede": "이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다.",
    "href": "/v1/digests/34"
  },
  "stats": { "currentsTracked": 6, "newThreads": 3, "storiesScanned": 18420 },
  "etag": "W/\"bv-34-20260628T0602\""
}
```

> 참고: `badge.hex`는 **상태색**(canon §2, steady=`#9BA3AF`)이고, `RankedRow.hex`는 **current 고유 hue**(canon §3/§8, `color_registry`)다. 둘은 다른 의미 차원이라 분리한다. `china`의 상태가 `steady`이므로 badge hex는 muted, current hex는 china blue `#4EA8DE`.
>
> 참고(라이브 vs 동결): 위 `ranked[].rank`는 이 `asOf`(2026-06-28T06:00) 기준 라이브 순위다. 같은 current의 **주간 동결 순위**는 digest(§3.3)의 `reshuffle[].thisRank`에서 별도로 본다 — 예시에서 `ai-governance`는 board 라이브 1위이고 issue 34 `thisRank`도 1이지만, 두 값은 source가 다르므로(`momentum_point` vs `weekly_rank`) 시점에 따라 갈릴 수 있다.

### 3.2 `CurrentView` — `GET /v1/currents/{id}` (canon `current_view`)

```ts
interface CurrentView {
  id: string;              // current.id (슬러그)
  name: string;            // current.name
  colorKey: string;        // current.color_key
  hex: string;             // color_registry.hex
  vertical: string;        // current.vertical_id
  status: CurrentStatus;   // current.status
  rank: number;            // current_view.rank
  state: MomentumState;    // current_view.state (4상태)
  badge: StateBadge;       // §3.1과 동일 규칙
  arc: ArcPoint[];         // current_view.arc jsonb — ~6개월 attention
  brief: Brief;            // current_view.brief jsonb (Citations API 바인딩)
  timeline: TimelineNode[];// current_view.timeline jsonb
  coverage: Coverage;      // current_view.coverage jsonb ('how it's covered')
  asOf: string;            // current_view.as_of (신선도 §4)
  reviewedAt: string;      // current_view.reviewed_at
  reviewedBy?: string;     // current_view.reviewed_by
  publishedAt: string;     // current_view.published_at
  isLastKnownGood: boolean;// current_view.is_last_known_good (§11)
  etag: string;            // current_view.etag
}

type CurrentStatus = "active" | "merged" | "dormant"; // current.status

interface ArcPoint {
  t: string;               // 버킷 ISO 날짜
  value: number;           // attention(정규화 volume)
  marker?: 1|2|3|4|5;      // arc[].marker — timeline[].node와 1:1 매핑(canon §6)
  eventId?: string;        // marker가 있을 때 timeline 동일 node와 공유(canon §6)
}

interface Brief {          // current_view.brief
  whatsHappening: string;
  whyItMatters: string;
  citations: Citation[];   // canon §9 Citations API — char span 하드바인딩
}
interface Citation {
  field: "whatsHappening"|"whyItMatters";
  quoteStart: number;      // 소스 본문 char span 시작
  quoteEnd: number;        // char span 끝
  articleId: string;       // article.id (is_canonical 정본)
  outlet: string;          // source_registry.outlet_name
  url: string;             // article.canonical_url
}

interface TimelineNode {   // current_view.timeline[] — 오래된→최신
  node: 1|2|3|4|5;         // timeline[].node = arc[].marker (canon §6)
  eventId: string;         // arc 동일 marker와 공유
  date: string;            // 이벤트 대표일 ISO
  text: string;            // 합성 요약(Citations 바인딩)
  isLatest: boolean;       // 최신 노드 강조(spec §2.2)
  sources: TimelineSource[];
}
interface TimelineSource {
  outlet: string;          // source_registry.outlet_name
  country: string;         // source_registry.country
  url: string;             // article.canonical_url
  articleId: string;       // article.id
}

interface Coverage {       // current_view.coverage — 결정적 룩업(canon §10)
  axes: ("region_block"|"outlet_type")[]; // coverage_axis
  minN: 5;                 // COVERAGE_MIN_N — 미달 버킷 숨김(불변)
  buckets: CoverageBucket[];
}
interface CoverageBucket {
  axis: "region_block"|"outlet_type";
  label: string;           // 버킷 라벨(current.coverage_config 정의)
  pct: number;             // outlet-unique·신디케이션 접은 후 비율(0..100)
  n: number;               // 표본수 (>= 5, 미달 시 버킷 자체 미포함)
}
```

**예시 응답 (`200`):**
```json
{
  "id": "ai-governance",
  "name": "AI governance",
  "colorKey": "ai-governance",
  "hex": "#F5A524",
  "vertical": "geopolitics",
  "status": "active",
  "rank": 1,
  "state": "rising",
  "badge": { "label": "rising", "icon": "ti-trending-up", "hex": "#F5A524" },
  "arc": [
    { "t": "2026-01-15", "value": 0.10 },
    { "t": "2026-02-10", "value": 0.18, "marker": 1, "eventId": "evt_eu_ai_act_enf" },
    { "t": "2026-03-22", "value": 0.27, "marker": 2, "eventId": "evt_us_eo_draft" },
    { "t": "2026-04-30", "value": 0.41, "marker": 3, "eventId": "evt_un_advisory" },
    { "t": "2026-05-28", "value": 0.55, "marker": 4, "eventId": "evt_g7_codex" },
    { "t": "2026-06-25", "value": 0.72, "marker": 5, "eventId": "evt_compute_treaty" }
  ],
  "brief": {
    "whatsHappening": "주요 관할권들이 프런티어 모델에 대한 구속력 있는 규칙으로 수렴하고 있다.",
    "whyItMatters": "분절적 규제가 글로벌 배포·컴퓨트 거버넌스의 비용 구조를 바꾼다.",
    "citations": [
      { "field": "whatsHappening", "quoteStart": 120, "quoteEnd": 188,
        "articleId": "art_9f2a", "outlet": "Reuters", "url": "https://www.reuters.com/tech/eu-ai-act-enforcement" }
    ]
  },
  "timeline": [
    { "node": 1, "eventId": "evt_eu_ai_act_enf", "date": "2026-02-10",
      "text": "EU가 고위험 시스템 집행 단계에 진입.", "isLatest": false,
      "sources": [ { "outlet": "Reuters", "country": "GB", "url": "https://www.reuters.com/tech/eu-ai-act-enforcement", "articleId": "art_9f2a" } ] },
    { "node": 5, "eventId": "evt_compute_treaty", "date": "2026-06-25",
      "text": "컴퓨트 임계 신고를 담은 다자 초안이 회람됨.", "isLatest": true,
      "sources": [ { "outlet": "Financial Times", "country": "GB", "url": "https://www.ft.com/content/compute-treaty", "articleId": "art_7c31" } ] }
  ],
  "coverage": {
    "axes": ["region_block", "outlet_type"],
    "minN": 5,
    "buckets": [
      { "axis": "region_block", "label": "EU",            "pct": 41, "n": 38 },
      { "axis": "region_block", "label": "North America", "pct": 33, "n": 29 },
      { "axis": "region_block", "label": "Asia",          "pct": 26, "n": 21 },
      { "axis": "outlet_type",  "label": "Wire",          "pct": 52, "n": 47 },
      { "axis": "outlet_type",  "label": "Newspaper",     "pct": 31, "n": 26 },
      { "axis": "outlet_type",  "label": "Broadcast",     "pct": 17, "n": 14 }
    ]
  },
  "asOf": "2026-06-28T06:00:00Z",
  "reviewedAt": "2026-06-28T05:40:00Z",
  "reviewedBy": "editor:hyejin",
  "publishedAt": "2026-06-28T05:42:00Z",
  "isLastKnownGood": false,
  "etag": "W/\"cv-ai-governance-v218\""
}
```

> **arc↔timeline 불변식(canon §6):** 모든 `arc[].marker`(1..5)는 정확히 하나의 `timeline[].node`(1..5)와 같고 `eventId`를 공유한다. 클라는 arc의 번호 마커를 탭하면 동일 `eventId`의 timeline 노드로 스크롤한다. marker 없는 arc 포인트는 단순 추세점.

### 3.3 `Digest` — `GET /v1/digests/{issue}` (canon `digest`)

```ts
interface Digest {
  issue: number;           // digest.issue (PK)
  weekOf: string;          // digest.week_of
  store: "published";      // digest.store (클라엔 published만)
  lede: string;            // digest.lede (serif, 1문장)
  reshuffle: ReshuffleRow[];// digest.reshuffle jsonb
  movers: Movers;          // digest.movers jsonb
  blurbs: Blurb[];         // digest.blurbs jsonb
  watchNext: string[];     // digest.watch_next
  stats: DigestStats;      // digest.stats jsonb
  publishedAt: string;     // digest.published_at
  etag: string;            // digest.etag
}
interface ReshuffleRow {   // weekly_rank 동결값 기반(week-over-week)
  currentId: string;       // current.id
  name: string;
  colorKey: string;        // current.color_key (라인 색)
  hex: string;
  lastRank: number;        // 지난주 weekly_rank.rank (동결)
  thisRank: number;        // 이번주 weekly_rank.rank (동결)
}
interface Movers {
  climber: { currentId: string; name: string; lastRank: number; thisRank: number; note: string };
  faller:  { currentId: string; name: string; lastRank: number; thisRank: number; note: string };
}
interface Blurb { kicker: string; body: string; }
interface DigestStats { currentsTracked: number; newThreads: number; storiesScanned: number; }
```

> **digest reshuffle source(canon §6):** `reshuffle`/`movers`의 `lastRank`/`thisRank`는 board의 라이브 순위가 **아니라** 주간 캡처된 `weekly_rank.rank`(불변·'보여진 사실')다. board(§3.1)가 매 `as_of` 라이브 순위를 보여주는 반면, digest는 주차 경계에서 동결된 순위 변동(week-over-week)을 회고한다. 두 source를 분리해 일중 흔들림이 주간 reshuffle을 오염시키지 않게 한다.

**예시 응답 (`200`):**
```json
{
  "issue": 34,
  "weekOf": "2026-06-22",
  "store": "published",
  "lede": "이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다.",
  "reshuffle": [
    { "currentId": "ai-governance", "name": "AI governance", "colorKey": "ai-governance", "hex": "#F5A524", "lastRank": 3, "thisRank": 1 },
    { "currentId": "cost-of-living", "name": "Cost of living", "colorKey": "cost-of-living", "hex": "#FB7A50", "lastRank": 1, "thisRank": 2 },
    { "currentId": "energy", "name": "Energy", "colorKey": "energy", "hex": "#34D0BA", "lastRank": 4, "thisRank": 3 },
    { "currentId": "climate", "name": "Climate", "colorKey": "climate", "hex": "#8B7FE8", "lastRank": 6, "thisRank": 4 },
    { "currentId": "middle-east", "name": "Middle East", "colorKey": "middle-east", "hex": "#7C9CC0", "lastRank": 2, "thisRank": 5 },
    { "currentId": "china", "name": "China", "colorKey": "china", "hex": "#4EA8DE", "lastRank": 5, "thisRank": 6 }
  ],
  "movers": {
    "climber": { "currentId": "climate", "name": "Climate", "lastRank": 6, "thisRank": 4, "note": "+2, 폭염·정책 동시 누적" },
    "faller":  { "currentId": "middle-east", "name": "Middle East", "lastRank": 2, "thisRank": 5, "note": "-3, 감속 국면" }
  },
  "blurbs": [
    { "kicker": "거버넌스", "body": "G7이 공동 코드 초안에 합의하며 규제 수렴이 가시화됐다." }
  ],
  "watchNext": [
    "다자 컴퓨트 조약 초안의 서명국 윤곽",
    "에너지-그리드 흐름의 병합 가능성"
  ],
  "stats": { "currentsTracked": 6, "newThreads": 3, "storiesScanned": 18420 },
  "publishedAt": "2026-06-22T07:00:00Z",
  "etag": "W/\"dg-34\""
}
```

### 3.4 매핑 요약표 (canon 테이블 → 응답 객체)

| 응답 객체 | canon 원천 | 비고 |
|---|---|---|
| `BoardView` | `board_view`(`is_current=true`) | share 서버정규화; `ranked`는 `momentum_point` **라이브** 투영(매 `as_of` `RANK() OVER (ORDER BY score DESC)`, momentum-engine §5.1). `weekly_rank` 아님 |
| `BoardView.ranked[].rank` | `momentum_point.score` (라이브 랭킹) | board 일중 갱신 가능. 주간 동결 `weekly_rank`는 digest 전용 |
| `BoardView.streamgraph` | `board_view.streamgraph` jsonb | 분모 `sum_volume_per_week`, `volume`=7일 EMA |
| `RankedRow.badge` | `momentum_point.state` + canon §2 | 색+아이콘+라벨, 색 단독 금지 |
| `CurrentView` | `current_view`(`store='published'`) | `arc/brief/timeline/coverage` 각 jsonb |
| `ArcPoint.marker` / `TimelineNode.node` | `arc[].marker`=`timeline[].node` | 1..5, `eventId` 공유 |
| `Brief.citations` | canon §9 Citations API | char span(`quoteStart/End`) 하드바인딩 |
| `Coverage` | `current_view.coverage` + `coverage_axis` | min-n=5 미달 버킷 미포함 |
| `Digest` | `digest` | `reshuffle`/`movers`는 `weekly_rank` **동결**(week-over-week). board 라이브 순위와 별개 |

---

## 4. 신선도 / 캐싱

### 4.1 publish → serve 전파
- 파이프라인이 휴먼게이트 통과분을 published store에 기록: `current_view(store='published')`, `board_view(is_current 토글)`, `digest`. 각 행에 `etag`·`as_of`·`published_at`(canon §6) 동봉.
- API는 published store만 읽으므로 전파 지연 = (publish 시각 → 캐시 무효화 + ISR 재생성) 합. **목표: board p95 staleness ≤ 5분**(canon §13).
- board의 `ranked` 순위는 새 `board_view` 발행 때마다 그 `as_of`의 `momentum_point.score`로 다시 랭킹된다(라이브). 즉 신선도는 "새 board_view가 얼마나 자주 발행되는가"에 직접 묶인다.
- ISR 재검증: **`ISR_REVALIDATE = 180s`** (canon §7, 허용범위 120~300). 즉 board/current 페이지는 최대 180초 stale 후 백그라운드 재생성. 트레이드오프: 짧을수록 신선·원본 부하↑ → 180s가 staleness 예산(5분) 내에서 부하 최소.
- 클라 폴링: **`POLL_INTERVAL = 60s`** (canon §7). board는 60초마다 `If-None-Match`로 재요청 → 대개 `304`, 새 라이브 순위가 발행됐으면 `200`+갱신.

### 4.2 ETag / Cache-Control
- **ETag** = canon `*.etag` 컬럼값. 약한 ETag(`W/"..."`) 사용(바이트 동일성 아닌 의미 동일성). 조건부요청 `If-None-Match` 일치 시 `304`.
- `Cache-Control`:
  | 리소스 | 헤더 |
  |---|---|
  | `/v1/board` | `public, max-age=60, stale-while-revalidate=120` |
  | `/v1/currents/{id}` (최신) | `public, max-age=60, stale-while-revalidate=180` |
  | `/v1/digests/{issue}` (과거) | `public, max-age=300, immutable` (issue는 불변·동결) |
  | `/v1/digests/{issue}` (최신) | `public, max-age=60` |
  | `/v1/search` | `private, max-age=30` (사용자 질의·개인화 여지) |
  | `/v1/watch*` | `no-store` (사용자 상태) |
- `stale-while-revalidate`로 폴링 클라가 즉시 캐시본을 받고 백그라운드 갱신 → 체감 지연 0.

### 4.3 'as of' 노출 (canon §7)
- 모든 신선도 민감 응답에 **`asOf`** 필드(= `board_view.as_of` / `current_view.as_of`)와 응답 헤더 `X-Meridian-As-Of: <ISO>`를 동시 노출. 클라는 "as of HH:MM" 라벨을 렌더(spec의 calm·competence 톤). board의 라이브 순위는 항상 이 `asOf` 시점 기준임을 라벨이 명시한다.
- `generatedAt`(board)·`publishedAt`(current/digest)도 별도 노출 → "데이터 기준시각(asOf)" vs "객체 생성/발행시각" 구분.

### 4.4 stale 처리
- **정상 stale:** ISR/SWR로 캐시본 서빙 중 백그라운드 갱신 — 사용자에 stale 표식 불필요(asOf로 충분).
- **발행 중단(high-risk fail-closed, canon §11):** 검증 실패로 신규 발행 차단 시 **last-known-good** 서빙:
  - current: `current_view.is_last_known_good=true` 행을 `200`으로 주되 응답 헤더 `Warning: 110 - "Response is stale"` + 본문 `isLastKnownGood:true` + `asOf`(과거값).
  - low-risk(색·정렬, canon §11 fail-open): 조용히 last-known-good 서빙.
  - board: 현행 `board_view` 없고 last-known-good도 없으면 `503 no_current_board` + `Retry-After: 60`.
- 클라 계약: `isLastKnownGood=true` 또는 `Warning: 110` 수신 시 "마지막 확인: {asOf}" 미세 표식, 강한 에러 UI는 띄우지 않는다(calm 원칙).

---

## 5. 페이지네이션 · 버전관리 · 에러모델 · 레이트리밋

### 5.1 페이지네이션 (search 전용)
- **커서 기반**(opaque cursor). board/current/digest는 단일 객체라 페이지네이션 없음.
- 요청: `?limit=20&cursor=<opaque>`. 응답:
  ```json
  { "items": [ /* SearchHit[] */ ],
    "page": { "limit": 20, "nextCursor": "eyJvZmYiOjIwfQ==", "hasMore": true } }
  ```
- `nextCursor=null` & `hasMore=false`이면 끝. 커서는 정렬키(score desc, id)를 인코딩 — offset 페이지네이션 대비 결과 흔들림에 안정적.

### 5.2 API 버전관리
- 경로 prefix **`/v1`** 고정(canon §7). 파괴적 변경은 `/v2` 신설로만. v1 내에서는 **additive-only**(필드·쿼리·enum 값 추가 허용, 기존 필드 제거/타입변경/의미변경 금지) — canon Phase 2 "상위 호환만" 정책과 정합.
- Deprecation 시 응답 헤더 `Deprecation: <date>` + `Sunset: <date>` + `Link: <.../v2/...>; rel="successor-version"`.
- enum(`MomentumState` 등)은 canon LOCK이라 v1 동안 불변.

### 5.3 공통 에러 envelope
모든 4xx/5xx는 동일 형태:
```ts
interface ErrorEnvelope {
  error: {
    code: string;        // 머신 판독용 안정 코드 (아래 표)
    message: string;     // 사람용 설명
    status: number;      // HTTP status 미러
    requestId: string;   // 추적용 (editorial_audit.request_id와 동일 체계)
    details?: object;    // 선택: 필드별 검증 오류 등
    retryAfter?: number; // 선택: 초 단위 (429/503)
  };
}
```
```json
{ "error": {
  "code": "current_not_found",
  "message": "No published current with id 'foo-bar'.",
  "status": 404,
  "requestId": "req_01J8...",
  "details": { "id": "foo-bar" }
} }
```

| code | HTTP | 발생 |
|---|---|---|
| `invalid_param` | 400 | 파라미터 형식 오류(`vertical`, 비정수 `issue` 등) |
| `missing_q` | 400 | search `q` 누락/공백 |
| `unauthorized` | 401 | watch 평면 인증 실패(Phase 1) |
| `current_not_found` | 404 | 미존재 슬러그 |
| `digest_not_found` | 404 | 미발행/미존재 issue |
| `current_gone` | 410 | dormant·후속 없음 |
| `unprocessable_param` | 422 | enum 위반(`type`/`vertical`) |
| `rate_limited` | 429 | 레이트리밋 초과 (`retryAfter` 동반) |
| `no_current_board` | 503 | 현행 board·LKG 모두 없음 |
| `internal_error` | 500 | 예기치 못한 서버 오류 |

`requestId`는 `editorial_audit.request_id`(canon §6)와 같은 식별 체계를 써서 변이↔서빙 오류를 한 추적ID로 상관.

### 5.4 레이트리밋
- 기본: **익명 IP 60 req/min**, **인증 사용자 600 req/min**(watch 포함). search는 더 엄격 **20 req/min/IP**(시맨틱 질의 비용).
- 폴링은 `POLL_INTERVAL=60s` 전제라 board 폴링은 분당 ~1회로 한도 내.
- 응답 헤더: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`(epoch). 초과 시 `429 rate_limited` + `Retry-After`.

---

## 6. merged / dormant current의 딥링크·리다이렉트

canon `current.status ∈ {active, merged, dormant}`, `current.merged_into`, 그리고 `current_lifecycle_event(type ∈ {spawn,split,merge,dormant,revive})`를 권위 소스로 사용.

- **merged:** `GET /v1/currents/{id}`에서 `status='merged'`면 **`301 Moved Permanently`** + `Location: /v1/currents/{merged_into}`. 영구 리다이렉트라 CDN·SEO·북마크가 후속 current로 수렴. 본문(선택)에 안내 envelope:
  ```json
  { "redirect": { "from": "evs", "to": "energy", "reason": "merge",
                  "occurredAt": "2026-05-10T00:00:00Z",
                  "lifecycleEventId": "lce_8831" } }
  ```
  `to`는 `merged_into` 체인을 **종단까지 따라가** 최종 active로 해소(merge 체인이 여러 단계여도 1홉으로 안내).
- **split:** 원본 current는 보통 한쪽으로 merge되거나 dormant. split 자체는 리다이렉트 대상이 아니라 `current_lifecycle_event(type='split')` 로그로 노출 — 응답에 `successors: [currentId...]`(related_current_id 기반)를 실어 클라가 "이 흐름은 다음으로 갈라졌습니다" 안내.
- **dormant:**
  - 후속(merge/split successor) 있으면 → `301`로 후속 안내(merged와 동일 처리).
  - 후속 없으면 → **`410 Gone`** + 본문에 `lastKnownGood`(마지막 published `CurrentView` 요약: name, 마지막 `asOf`, 최종 arc 말미)와 `lifecycleEventId`. dormant는 "조용히 사라짐"이라 강한 404 대신 410+회고를 준다. `revive` 이벤트 발생 시 다시 `active`로 복귀(같은 슬러그 안정, append-only).
- **딥링크 안정성:** `current.id`는 canon §4/§6에서 **주차간 안정·append-only**. 따라서 외부 공유 링크 `/current/{slug}`는 영구 유효하며, 상태 변화는 위 리다이렉트/410으로만 표현(슬러그 재사용·재발급 금지).

---

## 7. Search 백엔드 (시맨틱 + 전문 하이브리드) · 인덱스 대상

### 7.1 하이브리드 검색
- **시맨틱:** 질의 텍스트를 **BGE-M3**(`EMBED_MODEL=bge-m3`, `EMBED_REVISION=v1.5`, **1024d**, **cosine** `vector_cosine_ops`)로 임베딩 → pgvector **HNSW**(`m=16, ef_construction=64`, 질의 `ef_search=100`)로 top-k 최근접. canon §1과 동일 모델·인덱스(질의·색인 임베딩 공간 일치 필수).
- **전문(full-text):** Postgres `tsvector`/`websearch_to_tsquery` (`ts_rank_cd`) 또는 동급. 고유명사·정확 일치·짧은 질의를 시맨틱이 놓치는 경우 보강.
- **융합:** **Reciprocal Rank Fusion(RRF, k=60)** 로 두 랭킹 병합 →
  `score_final = 1/(60+rank_semantic) + 1/(60+rank_fulltext)`. 단순 가중합 대비 스케일 보정 불필요하고 한쪽 결측에 강건. 동점 tie-break: current면 momentum `score`(canon §3) desc.
- 임베딩은 **정본(`is_canonical=true`)에만** 존재(canon §1/§5)하므로 article 시맨틱 검색은 정본 코퍼스 한정, 결과는 `canonical_article_id`로 멤버십 해소.

### 7.2 인덱스 대상 (type별)
| `type` | 색인 텍스트 | 시맨틱 임베딩 | 전문 색인 | 비고 |
|---|---|---|---|---|
| `current` (default) | `current.name` + 최신 `current_view.brief`(whatsHappening/whyItMatters) | `current.centroid`(vector 1024) | name+brief tsvector | **사용자 1차 결과**. published만 |
| `event` | `event.summary` | `event.centroid`(1024) | summary tsvector | 만료 윈도(`expires_at`) 지난 event 제외 |
| `article` | `article.title` + `article.lede` | `article.embedding`(정본만, title+lede 기준 canon §1) | title+lede tsvector | 근거·딥링크용, 기본 미노출 |

> canon §1 LOCK: article 임베딩 대상 텍스트는 **title + lede**(추출 실패 시 title 단독). search 색인도 동일 텍스트를 사용해 질의-문서 표현 정합을 유지한다.

### 7.3 `SearchHit` 스키마 · 예시
```ts
interface SearchHit {
  type: "current" | "event" | "article";
  id: string;              // current.id / event.id / article.id
  title: string;           // current.name / event.summary / article.title
  snippet: string;         // 하이라이트 발췌
  score: number;           // RRF 융합 점수
  currentId?: string;      // event/article의 소속 current (딥링크용)
  colorKey?: string;       // current/소속 current 색
  state?: MomentumState;   // current일 때 momentum state
  href: string;            // "/v1/currents/{id}" 등 정규 딥링크
  asOf: string;            // 결과 신선도
}
```
```json
{
  "items": [
    { "type": "current", "id": "ai-governance", "title": "AI governance",
      "snippet": "주요 관할권들이 프런티어 모델 규칙으로 수렴…", "score": 0.0312,
      "currentId": "ai-governance", "colorKey": "ai-governance", "state": "rising",
      "href": "/v1/currents/ai-governance", "asOf": "2026-06-28T06:00:00Z" },
    { "type": "event", "id": "evt_g7_codex", "title": "G7 공동 코드 합의",
      "snippet": "G7이 공동 코드 초안에 합의…", "score": 0.0181,
      "currentId": "ai-governance", "colorKey": "ai-governance",
      "href": "/v1/currents/ai-governance?event=evt_g7_codex", "asOf": "2026-06-28T06:00:00Z" }
  ],
  "page": { "limit": 20, "nextCursor": null, "hasMore": false }
}
```

---

## 부록 A — 응답 코드 매트릭스

| 엔드포인트 | 200 | 301/302 | 304 | 400 | 401 | 404 | 410 | 422 | 429 | 503 |
|---|---|---|---|---|---|---|---|---|---|---|
| `GET /v1/board` | ● | – | ● | ● | – | – | – | – | – | ● |
| `GET /v1/currents/{id}` | ● | 301 merged | ● | – | – | ● | ● dormant | – | – | ● |
| `GET /v1/digests/{issue}` | ● | 302 latest | ● | ● | – | ● | – | – | – | – |
| `GET /v1/search` | ● | – | – | ● | – | – | – | ● | ● | – |
| `*/v1/watch*` (P1) | ●/204 | – | – | – | ● | ● | – | – | ● | – |

## 부록 B — canon 상수 사용 목록 (재발명 금지 확인)
`EMBED_MODEL=bge-m3`, `EMBED_REVISION=v1.5`, dim **1024**, **cosine/vector_cosine_ops**, HNSW `m=16/ef_construction=64/ef_search=100`, `momentum_state={rising,peaking,cooling,steady}`, 상태색 `#F5A524/#FB7A50/#7C9CC0/#9BA3AF` + `ti-trending-up/ti-activity/ti-trending-down/ti-minus`, `volume`=7일 EMA, score 가중치 `W_ACCEL=.30/W_PERSIST=.30/W_VOLUME=.25/W_SPREAD=.15`, `STATE_HYSTERESIS_DAYS=2`, `COVERAGE_MIN_N=5`, `coverage_axis={region_block,outlet_type}`, `ISR_REVALIDATE=180s`, `POLL_INTERVAL=60s`, 엔드포인트 4종 + watch(P1), arc.marker(1..5)=timeline.node(1..5).

> ranking source 분리(고정): **board `RankedRow.rank` = 매 `as_of` 라이브** `RANK() OVER (ORDER BY momentum_point.score DESC)`(momentum-engine §5.1/§5.2). **`weekly_rank`(동결·불변)는 digest `reshuffle`/`movers` 전용**(week-over-week). board는 모멘텀-우선 라이브 상태 뷰라 일중 갱신되고, digest는 주간 동결된 '보여진 사실'을 회고한다 — 둘은 서로 다른 source이며 값이 갈려도 정상이다.
