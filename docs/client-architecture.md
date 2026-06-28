# Meridian — Client Architecture (Frontend)

> **목적(한 줄):** Meridian의 3개 뷰(board · current · digest)를 다크 "intelligence terminal" 디자인으로, 순수 SVG+d3-shape 차트 / 모바일 우선 인터랙션 / RSC·ISR 페칭 경계 / 접근성·colorKey 거버넌스를 갖춘 Next.js 클라이언트로 구현하기 위한 설계서.
>
> **적용 범위:** Phase 0 (vertical 1개 `geopolitics`, 수동 큐레이션 ~10 currents, 8주 백필) 기준으로 전부 구속력. Phase 1 (+`technology`, 자동 합성·휴먼게이트) 동일 적용. Phase 2 (split/merge 자동 발견, 다언어) 상위 호환(컴포넌트 prop·팔레트 슬롯 추가만, 의미 변경 금지).
>
> 본 문서는 canon의 하위 문서다. **이름·값·상수는 canon을 그대로 재사용하며, 충돌 시 canon이 이긴다.** 모든 차트는 canon §8(순수 SVG+d3-shape, 호버 금지, 탭타깃 ≥44px, 데이터테이블 대체) 준수.

---

## 0. 레포 구조 / 모듈 경계

canon §6·spec §7의 디렉터리를 확정한다. 클라이언트는 published store(`board_view`/`current_view`/`digest`)만 읽고 파이프라인 테이블에 직접 접근하지 않는다.

```
web/                                  # Next.js 15 App Router, RSC 우선
  app/
    (board)/page.tsx                  # /  — board (home, ISR)
    currents/[id]/page.tsx            # /currents/{id} — current detail (ISR + SSR OG)
    digests/[issue]/page.tsx          # /digests/{issue} — digest (SSG/ISR, 동결)
    following/page.tsx                # CSR 셸 (Phase 1)
    search/page.tsx                   # CSR 셸 + 서버 액션 (Phase 1)
    onboarding/                       # 첫 실행 momentum 교육
    api/og/[...slug]/route.tsx        # OG 이미지 (satori/ImageResponse)
  components/
    charts/
      Streamgraph.tsx                 # 중앙 baseline 밴드
      AttentionArc.tsx                # 번호 마커 1..5 ↔ timeline 노드
      ReshuffleSlope.tsx              # last→this rank slope
      Sparkline.tsx                   # ranked row 미니 추세
      primitives/                     # <ChartFrame>, <DataTableFallback>, scales.ts
    momentum/MomentumBadge.tsx        # 아이콘+라벨+색 (색 단독 금지)
    board/ · current/ · digest/       # 뷰 컴포지션
  lib/
    api.ts                            # BFF fetch 래퍼(ETag·asOf 처리)
    query.ts                          # React Query client/keys
    freshness.ts                      # asOf → 'as of' 라벨·stale 판정
shared/                               # web ↔ (RN later) ↔ api 공유 (단일 진실원)
  tokens/                             # 디자인 토큰 (§10)
  types/                              # canon §6 미러 TS 타입
  palette/                            # color_registry 미러 + 배정 규칙
```

원칙: 차트는 **표현(presentation)만** 담당하고 share 정규화·정렬·랭킹은 서버(BFF)가 끝낸 값(`board_view.streamgraph`, `ranked`)을 그대로 그린다(canon §7 "share는 서버에서 정규화, 클라 비계산").

---

## 1. 차트 — 순수 SVG + d3-shape

공통 규칙(canon §8): `d3-scale`·`d3-shape`(path 생성기)만 의존하고 `d3-selection`/`d3-transition`(DOM 명령형 조작)은 쓰지 않는다 → RSC에서 문자열 path를 그대로 직렬화, 호버 리스너 없이 SSR. 모든 차트는 `<ChartFrame>`으로 감싸 `role="img"` + `aria-labelledby` + 시각적으로 숨긴 `<DataTableFallback>`을 동반한다.

### 1.0 공통 ChartFrame / 좌표계

```tsx
// components/charts/primitives/ChartFrame.tsx
export function ChartFrame({
  titleId, descId, title, desc, width, height, children, table,
}: ChartFrameProps) {
  return (
    <figure className="chart" role="group">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet"
           role="img" aria-labelledby={`${titleId} ${descId}`}>
        <title id={titleId}>{title}</title>
        <desc id={descId}>{desc}</desc>
        {children}
      </svg>
      {/* sr 전용 동등 데이터 — canon §8 데이터 테이블 대체 */}
      <div className="sr-only">{table}</div>
    </figure>
  );
}
```

- 좌표는 viewBox 기반 반응형(고정 px 아님). 모바일 기준 width=`360`, 밴드/슬로프 height=`220`, 아크 height=`200`.
- 색은 항상 `colorKey → color_registry.hex` 룩업(§6). 하드코딩 금지.

### 1.1 Streamgraph — 중앙 baseline 밴드 (board)

**역할(spec §2.1):** 6 currents × ~8주, 중앙 정렬 baseline 흐르는 밴드. magnitude(share) + movement 동시 전달.

**데이터 입력(canon 페이로드):** `GET /v1/board` → `board_view.streamgraph` (서버 정규화 share). 클라는 share 합산/정규화를 **하지 않는다**.

```ts
// shared/types/board.ts
interface BoardView {
  asOf: string;            // ISO — 신선도 (canon §7)
  generatedAt: string;
  etag: string;
  isCurrent: boolean;
  todaysRead: { text: string };
  streamgraph: {
    weeks: string[];                              // x축 라벨 (~8개, ISO week)
    series: { currentId: string; colorKey: string;
              name: string; state: MomentumState;
              share: number[] }[];                // 0..1, 주별, 서버 정규화
  };
  ranked: RankedRow[];
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
}
type MomentumState = 'rising' | 'peaking' | 'cooling' | 'steady'; // canon §2 (4상태)
```

**구현:** `d3-shape`의 `stack()` + `stackOffsetSilhouette`(중앙 baseline) + `stackOrderInsideOut`, area는 `area().curve(curveBasis)` (밴드 가독성용 완만한 곡선).

```tsx
const stackGen = stack<Week>()
  .keys(series.map(s => s.currentId))
  .value((d, key) => d[key])
  .offset(stackOffsetSilhouette)       // 중앙 baseline
  .order(stackOrderInsideOut);
const x = scaleLinear().domain([0, weeks.length - 1]).range([pad, W - pad]);
const y = scaleLinear().domain(yExtent(stacked)).range([H - pad, pad]);
const areaGen = area<SeriesPoint>()
  .x((_, i) => x(i)).y0(d => y(d[0])).y1(d => y(d[1])).curve(curveBasis);
// 각 밴드: <path d={areaGen(layer)} fill={hexOf(colorKey)} />
```

- 호버 금지 → 밴드 위에 **상시 인라인 라벨**(밴드가 가장 두꺼운 주의 중앙에 current name, ≥12px). tap 시 해당 current로 라우팅(`/currents/{id}`).
- 6 currents 목업 vs 10~15 원칙의 가독성은 §6에서 처리(밴드 수 상한·정렬).

### 1.2 Attention Arc — 번호 마커 1..5 (current detail)

**역할(spec §2.2):** ~6개월 attention area/line + 번호 이벤트 마커 1..5. 마커 ↔ timeline 노드 1..5는 `eventId` 공유(canon §6 "arc↔timeline 매핑: arc[].marker(1..5)=timeline[].node(1..5), 양쪽 eventId 공유").

**데이터 입력:** `GET /v1/currents/{id}` → `current_view`(Published store, §6).

```ts
interface CurrentView {
  currentId: string; name: string; colorKey: string; rank: number;
  state: MomentumState; asOf: string; etag: string;
  isLastKnownGood: boolean;                         // canon §11
  arc: { eventId: string; marker: number;           // 1..5
         points: { t: string; value: number }[] }[]; // 시계열은 jsonb
  brief: { whatsHappening: string; whyItMatters: string };
  timeline: { node: number; eventId: string; date: string; text: string;
              sources: { outlet: string; url: string }[] }[];
  coverage: { buckets: { axis: 'region_block'|'outlet_type';
                         label: string; pct: number; n: number }[] }; // §10
}
```

**구현:** 단일 연속 시계열은 `arc[].points`를 시간순 평탄화. `area().curve(curveMonotoneX)`로 면, `line()`로 상단 스트로크(current colorKey hue). 마커는 각 `arc[i].marker` 위치(해당 event 피크 t)에 번호 원.

```tsx
// 마커: 탭타깃 ≥44px (canon §8). 시각 원은 작게, 히트영역은 44px 투명 원.
<g role="listitem" aria-label={`Moment ${m.marker}: ${dateLabel}`}>
  <circle cx={cx} cy={cy} r={22} fill="transparent"          // 44px hit area
          tabIndex={0} onClick={() => scrollToNode(m.marker)} />
  <circle cx={cx} cy={cy} r={10} fill={hex} stroke="var(--bg)" />
  <text x={cx} y={cy} dy="0.35em" textAnchor="middle"
        fontSize={11} fill="var(--bg)">{m.marker}</text>
</g>
```

- 마커 tap → 동일 `eventId`의 timeline 노드로 스크롤·하이라이트(상호 anchoring). 키보드: 마커들은 `role="list"`의 항목으로 Tab 순회.

### 1.3 Reshuffle Slope Chart — last→this rank (digest)

**역할(spec §2.3):** 지난주 rank → 이번주 rank, current별 색 라인. "movement"의 시그니처 비주얼.

**데이터 입력:** `GET /v1/digests/{issue}` → `digest.reshuffle` (canon §6, weekly_rank 동결값 기반).

```ts
interface Digest {
  issue: number; weekOf: string; etag: string; publishedAt: string;
  lede: string;                                       // serif
  reshuffle: { currentId: string; name: string; colorKey: string;
               lastRank: number; thisRank: number }[];
  movers: { climberId: string; fallerId: string };
  blurbs: { kicker: string; body: string }[];
  watchNext: string[];
  stats: { currentsTracked: number; newThreads: number; storiesScanned: number };
}
```

**구현:** 좌(lastRank)·우(thisRank) 2열 카테고리 축. rank는 1이 위. `scalePoint` 또는 `scaleLinear([1, maxRank] → [top, bottom])`. 각 current는 `line([[xL, y(last)], [xR, y(this)]])` 직선 + 양끝 라벨.

```tsx
const yRank = scaleLinear().domain([1, maxRank]).range([pad, H - pad]); // 1=top
// 상승=위로(기울기 음수), 하락=아래로. 색=colorKey, 굵기는 |Δrank| 비례(가독 한계 4px)
<line x1={xL} y1={yRank(d.lastRank)} x2={xR} y2={yRank(d.thisRank)}
      stroke={hexOf(d.colorKey)} strokeWidth={2 + Math.min(2, Math.abs(delta)/2)} />
```

- 색만으로 방향 인코딩 금지 → 라벨에 `↑3 / ↓2` 텍스트 + 화살표 아이콘 동반(접근성 §5).
- digest는 발행 후 **동결**(weekly_rank 불변, canon §6) → SSG/ISR로 정적화(아래 §3).

---

## 2. 모바일 인터랙션

canon §8 "호버 의존 금지, 탭타깃 ≥44px". 모바일 우선, 데스크톱은 동일 인터랙션 위에 키보드만 추가.

| 규칙 | 구현 |
|------|------|
| **호버 금지** | 모든 정보는 상시 표시 or tap-to-reveal. `:hover` 스타일은 `@media (hover: hover) and (pointer: fine)`로만 진보적 향상. 차트 툴팁은 hover 미사용. |
| **탭타깃 ≥44px** | 아크 마커·뱃지·탭바·source 링크 모두 최소 히트영역 `min-block-size:44px; min-inline-size:44px`. 시각 요소는 작아도 투명 히트영역 44px(아크 마커 r=22). |
| **tap-to-reveal** | 스트림 밴드 라벨/coverage 막대 수치/timeline source 목록은 tap 시 확장(`<details>`/`aria-expanded` 토글, JS 없이 동작 가능한 `<details>` 우선). |
| **reduced-motion** | `@media (prefers-reduced-motion: reduce)` → 차트 라인 draw 애니메이션·스트림 전이 제거, 즉시 최종 상태 렌더. 온보딩 시연도 정적 폴백. |

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: .001ms !important; transition-duration: .001ms !important; }
  .arc-draw { stroke-dasharray: none; }   /* draw-on 효과 비활성 */
}
.tab-target { min-block-size: 44px; min-inline-size: 44px;
              display: inline-flex; align-items: center; }
```

- 스크롤 위주 내비게이션, 제스처 의존(스와이프 only) 기능 금지 → 모든 동작에 명시적 탭 대안.

---

## 3. 렌더링 / 페칭 경계 — RSC/ISR vs CSR

canon §7: REST + 뷰별 BFF 단일 콜, ETag/HTTP 캐시 + ISR(`ISR_REVALIDATE=180s`, 범위 120~300), 응답 `asOf` 노출, 클라 폴링 `POLL_INTERVAL=60s`.

| 뷰 | 렌더 전략 | 근거 |
|----|----------|------|
| **board** `/` | RSC + **ISR 180s** (`export const revalidate = 180`), 클라 컴포넌트가 폴링 60s로 신선화 | 라이브 상태지만 초단위 불필요 → ISR로 CDN 캐시 + 60s 폴링으로 'as of' 갱신 |
| **current** `/currents/{id}` | RSC + ISR 180s + `generateMetadata`(OG·SEO) | 거의 정적, 발행 시 갱신. SEO/공유 필요 → SSR 메타 |
| **digest** `/digests/{issue}` | **SSG/ISR**(발행 후 동결) `generateStaticParams` + 긴 revalidate | weekly_rank·digest는 불변(canon §6) → 사실상 정적, 공유 트래픽 多 |
| **following** | **CSR** 셸(개인화, anti-bubble: board는 절대 안 가림) | 사용자별 → 캐시 불가, 클라 페치 |
| **search** | CSR + 서버 액션/route handler 프록시 `GET /v1/search?q=` | 입력 의존, 캐시 가치 낮음 |
| **onboarding** | 정적 클라 컴포넌트 | 데이터 없음 |

### 3.1 board live 갱신 — ISR + 폴링 + 'as of'

```tsx
// app/(board)/page.tsx  (RSC)
export const revalidate = 180;                        // ISR_REVALIDATE (canon §7)
export default async function BoardPage() {
  const initial = await fetchBoard();                 // 서버 1콜, BoardView
  return <BoardLive initial={initial} />;             // 클라가 폴링 인계
}
```

```tsx
// components/board/BoardLive.tsx  (client)
'use client';
function BoardLive({ initial }: { initial: BoardView }) {
  const { data } = useQuery({
    queryKey: ['board'],
    queryFn: fetchBoard,
    initialData: initial,
    refetchInterval: 60_000,                           // POLL_INTERVAL=60s
    refetchOnWindowFocus: true,
    staleTime: 60_000,
  });
  return (<><FreshnessBadge asOf={data.asOf} isCurrent={data.isCurrent} />
            <Streamgraph data={data.streamgraph} /> <RankedList rows={data.ranked} /></>);
}
```

- BFF fetch는 **ETag 조건부 요청**(`If-None-Match`) → 304면 페이로드 0, asOf만 신선. p95 staleness ≤ 5분(canon §13)은 ISR 180s + 폴링 60s로 충족.

### 3.2 상태관리 — React Query

- **React Query(TanStack Query v5)** 채택. 서버 상태(board/current/digest/search) 캐시·폴링·재시도·stale 관리 일원화. 클라 전역 상태(onboarding 완료, following 목록 로컬)는 가벼운 `zustand` or React context — Redux 불채택(서버 상태가 대부분이라 과설계).
- query keys: `['board']`, `['current', id]`, `['digest', issue]`, `['search', q]`. ETag는 fetch 래퍼가 메모리 보관.
- `digest`/`current`는 `staleTime` 길게(발행 동결), `board`만 짧게.

---

## 4. 로딩 / 빈 / 에러 / stale + 신선도 표시

각 뷰는 4상태를 명시적으로 처리. canon §11 last-known-good 노출이 핵심.

| 상태 | 처리 |
|------|------|
| **loading** | 스켈레톤(차트 자리 = 회색 밴드 플레이스홀더, layout shift 0). RSC 첫 페인트는 서버 데이터로 즉시 채움 → 폴링 재검증만 백그라운드. |
| **empty** | board에 currents 0개(Phase 0 초기): "아직 추적 중인 흐름이 없습니다" + 마지막 갱신 시각. current arc 데이터 부족 시 "데이터 축적 중(8주 백필)". |
| **error** | BFF 5xx/네트워크: 마지막 성공 캐시를 계속 표시 + 비차단 배너 "최신 갱신 실패 — 마지막 데이터 표시 중". React Query `retry: 2` + 지수 백오프. |
| **stale** | `asOf`가 임계 초과 시 'as of' 라벨을 amber로 강조. `current_view.is_last_known_good=true` 또는 `board_view.is_current=false`면 "확정 전 마지막 검증본" 라벨(canon §11 fail-open 서빙). |

```ts
// lib/freshness.ts
const STALE_AFTER_MS = 5 * 60_000;            // canon §13 p95 staleness ≤ 5분
export function freshness(asOf: string, isCurrent = true) {
  const age = Date.now() - Date.parse(asOf);
  return {
    label: `as of ${formatTime(asOf)}`,         // canon §7 asOf 노출
    isStale: age > STALE_AFTER_MS || !isCurrent,
  };
}
```

```tsx
function FreshnessBadge({ asOf, isCurrent }: { asOf: string; isCurrent: boolean }) {
  const f = freshness(asOf, isCurrent);
  return <span className={f.isStale ? 'fresh fresh--stale' : 'fresh'}
               aria-live="polite">{f.label}{f.isStale && ' · 갱신 지연'}</span>;
}
```

---

## 5. 접근성

canon §8: 다크테마 WCAG 비텍스트 3:1, 색 단독 인코딩 금지, 차트 스크린리더 대체.

### 5.1 다크테마 대비비

- 본문 텍스트 `--ink #F2F4F7` on `--bg #0E1116` ≈ 15.8:1 (WCAG AAA). `--secondary #9BA3AF` on bg ≈ 6.9:1 (AA). `--muted #6B7480`은 캡션 한정(대형 텍스트/비핵심), 본문 금지.
- **비텍스트(차트 밴드·라인·뱃지 테두리)** 인접 색 대비 ≥ 3:1 보장 — 팔레트 QA 게이트(§6, canon §8 colorblind+대비 QA)에서 강제.

### 5.2 색 단독 인코딩 금지 (momentum)

canon §2: 항상 아이콘+라벨 동반. `MomentumBadge`는 3중 인코딩(아이콘+라벨+색).

```tsx
const MOMENTUM = {
  rising:  { hex:'#F5A524', icon:'ti-trending-up',   label:'Rising'  },
  peaking: { hex:'#FB7A50', icon:'ti-activity',      label:'Peaking' },
  cooling: { hex:'#7C9CC0', icon:'ti-trending-down', label:'Cooling' },
  steady:  { hex:'#9BA3AF', icon:'ti-minus',         label:'Steady'  },
} as const;                                          // canon §2 값 고정

function MomentumBadge({ state }: { state: MomentumState }) {
  const m = MOMENTUM[state];
  return <span className="badge tab-target" style={{ color: m.hex }}>
    <i className={m.icon} aria-hidden /> <span>{m.label}</span>   {/* 라벨 = 접근명 */}
  </span>;
}
```

### 5.3 차트 스크린리더 대체

- 모든 차트는 `<DataTableFallback>`(시각 숨김, sr 노출) 제공 — canon §8.
  - Streamgraph → `<table>`: 행=current, 열=week, 셀=share%.
  - Arc → `<table>`: 마커 1..5 / 날짜 / value / 연결 timeline 노드.
  - Slope → `<table>`: current / lastRank / thisRank / Δ.
- `<svg role="img">`에 `<title>`+`<desc>`(요약문: "AI governance가 8주간 share 18→27%로 rising").

### 5.4 키보드

- 탭바·뱃지·아크 마커·source 링크·tap-to-reveal `<details>` 모두 `tabindex` 자연 순서. 포커스 링 `outline: 2px solid var(--brand-teal); outline-offset: 2px` (대비 충족).
- 아크 마커는 `role="list"`/`listitem`, Enter/Space로 해당 timeline 노드 이동.

---

## 6. colorKey 거버넌스 — 6색 → 12(+예비 3) 팔레트

**문제:** spec §3은 6 hue만 정의하지만 board는 10~15 currents(spec §1). canon §8은 "활성 12색(+예비 3, 최대 15), current당 hue 동결·중앙 거버넌스 배정(append-only), 모멘텀 의미색과 충돌 hue 제외, colorblind+대비 QA 통과"를 요구한다.

### 6.1 단일 진실원

`color_registry(color_key PK, hex, hue_name, is_reserved)` (canon §6)가 유일 출처. 클라는 `shared/palette/`에 이 테이블을 **미러**하고 직접 hex를 발명하지 않는다. current의 색은 `current.color_key → color_registry.hex`로만 해소.

### 6.2 팔레트 확장안 (대비 유지)

기존 6색(spec §3)을 그대로 활성 슬롯 1~6으로 두고, 모멘텀 의미색(up-green `#6FBF73`, down-red `#D08585`, canon §8)과 hue 충돌하는 녹/적 계열을 **제외**한 6개 hue를 추가해 활성 12 + 예비 3을 채운다. 각 신규 색은 `--bg #0E1116` 대비 비텍스트 ≥3:1, colorblind(deuteranopia/protanopia) 구분 게이트 통과.

```ts
// shared/palette/registry.ts — color_registry 미러 (append-only)
export const COLOR_REGISTRY = [
  // 활성 1..6 (spec §3, 기존)
  { colorKey:'ai-governance', hex:'#F5A524', hueName:'amber',  reserved:false },
  { colorKey:'cost-of-living',hex:'#FB7A50', hueName:'coral',  reserved:false },
  { colorKey:'energy',        hex:'#34D0BA', hueName:'teal',   reserved:false },
  { colorKey:'middle-east',   hex:'#7C9CC0', hueName:'steel',  reserved:false },
  { colorKey:'china',         hex:'#4EA8DE', hueName:'blue',   reserved:false },
  { colorKey:'climate',       hex:'#8B7FE8', hueName:'violet', reserved:false },
  // 활성 7..12 (확장 — up-green/down-red hue 회피, 대비+CB QA 통과)
  { colorKey:'slot-07', hex:'#C792EA', hueName:'orchid',     reserved:false },
  { colorKey:'slot-08', hex:'#56B6C2', hueName:'cyan',       reserved:false },
  { colorKey:'slot-09', hex:'#E6A23C', hueName:'gold',       reserved:false },
  { colorKey:'slot-10', hex:'#B0A4F5', hueName:'periwinkle', reserved:false },
  { colorKey:'slot-11', hex:'#7FB0E0', hueName:'sky',        reserved:false },
  { colorKey:'slot-12', hex:'#D98AC0', hueName:'magenta',    reserved:false },
  // 예비 13..15 (reserved=true, 배정 보류)
  { colorKey:'slot-13', hex:'#9AA7B4', hueName:'slate',  reserved:true },
  { colorKey:'slot-14', hex:'#C0B283', hueName:'sand',   reserved:true },
  { colorKey:'slot-15', hex:'#86C5C0', hueName:'aqua',   reserved:true },
] as const;
```

> 트레이드오프: 신규 hex(slot-07..15)는 **잠정 제안값**이며 서버 `color_registry`가 최종 진실원이다 — 클라는 미러를 빌드시 서버값으로 검증(불일치 시 빌드 실패)해 발명 방지. 녹/적 회피는 모멘텀 색과의 의미 혼선 차단이 가독성보다 우선이기 때문.

### 6.3 배정 규칙 (append-only)

- current당 hue **동결**: 한 번 배정된 `color_key`는 그 current 수명 내내 불변(canon §4 ID 안정성·append-only와 정합). 재군집/리랭크가 색을 바꾸지 않는다.
- 신규 current → 중앙 거버넌스가 활성 슬롯 중 미사용 hue를 배정. 활성 12 소진 시 예비 3 승격(`is_reserved=false`).
- `merged` current(`merged_into`)는 색을 흡수처에 양도하지 않고 자기 색을 동결 유지(digest reshuffle 연속성).

### 6.4 '6 currents 목업 vs 10~15 원칙' 시각 정합성

- **Streamgraph 밴드 가독성:** 8주 × 15밴드는 얇아져 라벨 충돌. 규칙 — 스트림은 **상위 N=8 밴드만**(score 내림차순, canon §3) 그리고 나머지는 "Other" 단일 회색 밴드로 합산(서버 `streamgraph.series`가 이미 잘라 보냄 가정, 클라 비계산). 목업 6 currents는 N=8 이하라 그대로 표시.
- **ranked list**는 전체 10~15 표시(밴드 제한과 분리) — 리스트는 행 높이 ≥44px라 15개도 가독.
- **slope chart**는 digest에서 ~6개(spec §2.3 "~6 currents")만 — 이동이 큰 상위만 그려 라인 교차 가독 유지.
- 인접 밴드/라인 색 대비 3:1은 §6.2 QA가 인접 슬롯 hue 거리로 보장.

---

## 7. current / digest SSR·SEO·OG 공유

- **SSR 메타:** `app/currents/[id]/page.tsx`·`app/digests/[issue]/page.tsx`는 `generateMetadata`로 title/description/canonical/OG/Twitter 카드 생성. board 데이터(이름·state·lede)에서 채움.

```tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const cv = await fetchCurrent(params.id);
  return {
    title: `${cv.name} — Meridian`,
    description: cv.brief.whatsHappening.slice(0, 155),
    openGraph: { images: [`/api/og/current/${cv.currentId}`], type: 'article' },
    twitter: { card: 'summary_large_image' },
    alternates: { canonical: `/currents/${cv.currentId}` },
  };
}
```

- **OG 이미지:** `app/api/og/[...slug]/route.tsx` = Next `ImageResponse`(satori). 다크테마 카드에 current name + MomentumBadge(아이콘+라벨+색) + 미니 아크 스냅샷. digest OG는 issue 번호 + serif lede + reshuffle 미리보기. 정적 캐시(`Cache-Control: public, immutable`)로 공유 트래픽 흡수.
- **SEO:** current/digest는 ISR로 사전 렌더 → 크롤러가 완성 HTML 수신. JSON-LD `NewsArticle`(digest) 추가. board는 anti-bubble 홈으로 index 허용, following/search는 `robots: noindex`.

---

## 8. 온보딩 — momentum 어휘 교육 (첫 실행)

canon §2의 4상태 어휘(rising/peaking/cooling/steady)를 첫 실행에 교육. spec §5.2 "제품이 plain language로 이 구분을 가르친다".

- 트리거: `localStorage 'meridian.onboarded'` 미존재 시 board 첫 진입에서 3스텝 오버레이(스킵 가능, 탭타깃 ≥44px).
- 각 스텝 = MomentumBadge 실물 + 한 줄 정의:
  - **Rising** — "가속 중. 관심이 빨라지고 있어요." (`d1>0, d2≥0`)
  - **Peaking** — "정점 부근. 높지만 평탄해지는 중." (`d1≈0, d2<0`)
  - **Cooling** — "식는 중. 관심이 줄고 있어요." (`d1<0`)
  - **Steady** — "꾸준함. 극적 사건 없이 baseline 유지." (canon §2 steady)
- reduced-motion 시 애니메이션 없는 정적 카드. 동일 어휘를 board 뱃지에 `aria-label`로 재사용(학습 전이).
- 'no dramatic event — just steady accumulation' 카피(spec §5.2)로 spike vs accumulation 차이 강조.

---

## 9. Search / Following 탭 — 클라이언트 동작 (Phase 구분)

| 탭 | Phase 0 | Phase 1 | Phase 2 |
|----|---------|---------|---------|
| **Search** | 탭은 노출하되 **비활성/Coming soon**(엔드포인트 미보장). 또는 클라 측 현재 board currents 이름 필터만. | `GET /v1/search?q=`(canon §7) 연동, CSR 디바운스(300ms) 입력 → 결과 카드(current 링크). | 다소스·다언어 검색 확장. |
| **Following** | 로컬 전용 watch 목록(`localStorage`), "Alert me when this moves" 토글 상태 보관. board는 절대 안 가림(anti-bubble, spec §1). | watch 서버 동기화·알림(spec Phase1 "Watch/alerts"). | 개인화(절대 board 비은닉). |

- Search: CSR, React Query `['search', q]`, `enabled: q.length >= 2`, 빈 입력 시 추천 currents. 결과는 current 카드(MomentumBadge 포함).
- Following: 클라 상태(zustand) + Phase1부터 서버. anti-bubble 불변식은 라우팅 레벨에서 board를 개인화로 대체 불가하게 강제.

---

## 10. 디자인 토큰을 shared/ 로

spec §7 `shared/`는 web ↔ (RN later) ↔ api 공유 단일 진실원. 토큰을 프레임워크 중립 형태로 둔다.

```
shared/tokens/
  color.ts        # 표면/텍스트/브랜드/status (spec §3 그대로)
  momentum.ts     # canon §2 4상태 hex+icon+label (단일 정의)
  palette.ts      # color_registry 미러 (§6) — 서버 검증 대상
  type.ts         # sans 전역, serif=digest lede 한정 (spec §3)
  index.ts        # build → css vars + TS export
```

```ts
// shared/tokens/color.ts — spec §3 토큰 (값 변형 금지)
export const COLOR = {
  bg:'#0E1116', card:'#171C24', cardAlt:'#13171D', border:'#2C333D',
  ink:'#F2F4F7', secondary:'#9BA3AF', muted:'#6B7480',
  brandTeal:'#34D0BA', upGreen:'#6FBF73', downRed:'#D08585',
} as const;
```

- 빌드 시 `shared/tokens/index.ts`가 (a) `:root` CSS custom properties(`--bg` 등 spec §3 이름 그대로), (b) TS 상수 두 산출물 생성 → CSS와 TS가 같은 진실원 사용.
- RN 전환 대비: 토큰은 플랫폼 비의존 객체. web은 CSS vars로, RN은 JS 객체로 소비.
- 규칙: 컴포넌트는 raw hex 금지, 반드시 토큰/registry 참조. 모멘텀 색은 `shared/tokens/momentum.ts` 단일 정의만 import(canon §2 값과 1:1).

---

## 부록 A — 컴포넌트 ↔ canon 페이로드 매핑

| 컴포넌트 | 엔드포인트 (canon §7) | 입력 필드 |
|----------|----------------------|-----------|
| Streamgraph | `GET /v1/board` | `board_view.streamgraph.{weeks,series[].share}` |
| RankedList + MomentumBadge | `GET /v1/board` | `board_view.ranked[]`, `state`(4상태) |
| FreshnessBadge | `GET /v1/board` | `asOf`, `isCurrent` |
| AttentionArc | `GET /v1/currents/{id}` | `current_view.arc[].{marker,eventId,points}` |
| Timeline | `GET /v1/currents/{id}` | `current_view.timeline[].{node,eventId,sources}` |
| CoverageBars | `GET /v1/currents/{id}` | `current_view.coverage.buckets`(min-n=5 숨김, canon §10) |
| ReshuffleSlope | `GET /v1/digests/{issue}` | `digest.reshuffle[].{lastRank,thisRank,colorKey}` |

## 부록 B — 확정 상수 (canon 재사용)

| 상수 | 값 | 출처 |
|------|-----|------|
| `ISR_REVALIDATE` | 180s (120~300) | canon §7 |
| `POLL_INTERVAL` | 60s | canon §7 |
| p95 staleness | ≤ 5분 | canon §13 |
| 탭타깃 최소 | 44px | canon §8 |
| 비텍스트 대비 | ≥ 3:1 | canon §8 |
| 활성 팔레트 | 12 (+예비 3, 최대 15) | canon §8 |
| momentum 4상태 | rising/peaking/cooling/steady | canon §2 |
| arc↔timeline 마커 | 1..5, eventId 공유 | canon §6 |
| coverage min-n | `COVERAGE_MIN_N=5` | canon §10 |
