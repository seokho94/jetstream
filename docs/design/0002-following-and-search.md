# 0002 — Following & Search (`0002-following-and-search.md`)

> **권위:** [CANON](CANON.md) **§14 R14**가 본 문서의 Phase 0 범위를 고정한다. 충돌 시 CANON이 이긴다.
> 관련: CANON **R13**(watch 토글) · **§2.1**(anti-bubble) · [api-contract](api-contract.md) **§2.4/§2.5/§7**.

> **목적 (한 줄):** 탭바의 두 보조 표면 **Following**(= watch 집합)과 **Search**를 anti-bubble 제약 아래 정의하고, 임베딩 없이 지금 구현 가능한 Phase 0 범위를 고정한다.

---

## 1. Following — watch 집합의 클라 표면

**정의.** "Following"은 새로운 개인화 축이 아니라, 사용자가 board에서 켠 **current watch 집합**(CANON R13)의 전용 화면이다. 별도의 팔로우 그래프·피드가 아니다.

**anti-bubble 가드 (LOCK, §2.1).**
- board(Currents 탭)는 **항상 전세계** — Following은 board를 대체하거나 축소하지 않는 **보조 렌즈**다.
- 개인화가 전세계 뷰를 **숨기지 않는다**. Following은 "내가 표시한 흐름 + 그 변화"만 모아 보여줄 뿐, 그 외 흐름을 가리지 않는다.
- 대상은 **watched currents만**. 인물·기관·지역 등 엔티티/토픽 팔로우는 (버블 리스크·엔티티 인프라 미비로) **비채택**.

**저장.**
| | Phase 0 (구현) | Phase 1 |
|---|---|---|
| watch 집합 | localStorage `jetstream.watch` (currentId[]) | `GET /v1/watch`, `PUT/DELETE /v1/watch/{currentId}` + 인증 (§2.5) |
| 변화 추적 | localStorage `jetstream.watch.seen` (currentId→마지막 방문 상태) | 서버 last-seen / 푸시 |

`current_view`는 사용자 무관 공유 발행 객체라 watch 상태를 담지 않는다(R13) — watch는 **클라 오버레이**.

**화면.**
- watched current 행: tick·이름·sparkline·**상태 배지**·`›`. board 랭킹 행과 동일 어포던스(행 전체 탭).
- **상태변화 배지("변화")**: 마지막 방문(`seen`) 대비 momentum state가 바뀐 흐름에 표시 → "내가 보는 동안 무엇이 움직였나".
- **빈 상태**: "아직 주목한 흐름이 없어요 — 흐름 상세의 알림 토글을 켜세요" + board로 유도.

**"moves"의 의미(§3).** watch 알림 트리거 = 대상 current의 `momentum_point.state` 전환이 **2일 연속 확정**(`STATE_HYSTERESIS_DAYS=2`). 일별 흔들림이 아니다. Phase 0은 in-app **변화 표시**, Phase 1은 푸시/이메일.

---

## 2. Search

**Phase 0 (구현, 임베딩 없이).**
- 색인 대상: **current**(name + `brief.whatsHappening`/`whyItMatters`) + **grounded timeline event**(`current_view.timeline[].text`, placeholder "보도 집중" 노드 제외).
- 매칭: Postgres **ILIKE 부분일치**(한국어·영문 모두 동작, 소규모 코퍼스에 충분).
- 응답: `SearchHit[]` (아래) — `current` 히트와 `event` 히트.

```ts
interface SearchHit {           // shared/src/types.ts
  type: "current" | "event";
  id: string;                   // current.id  |  `${currentId}:${date}`
  currentId: string;            // 클릭 → /current/{currentId}
  title: string;                // current.name | event 요약문
  snippet: string;              // brief 요약 | `${흐름명} · ${date}`
  colorKey: string;             // 흐름 hue (CANON R11)
  state?: MomentumState | null; // current 히트만
  date?: string | null;         // event 히트만
  url?: string | null;          // event 히트의 대표 출처 딥링크
}
```

**Phase 1 (상위호환 승격, api-contract §7).**
- **시맨틱**: 질의 → BGE-M3(1024d) → pgvector HNSW(`ef_search=100`).
- **전문**: tsvector / `websearch_to_tsquery` (`ts_rank_cd`).
- **융합**: RRF(k=60). 동점 tie-break = current면 momentum score.
- 색인에 **article**(title+lede, 정본 한정) 추가, 커서 페이지네이션(§5.1).
- Phase 0 `SearchHit`는 §7.3 `SearchHit`의 **부분집합** — 필드 추가만, 의미 변경 없음.

**엔드포인트.** `GET /v1/search?q=` → `{ q, results: SearchHit[] }`. `X-Data-Source`, `Cache-Control: private, max-age=30`(§4.2). 빈 `q` → 빈 결과(Phase 0 완화; §5 `missing_q 400`·레이트리밋·커서는 Phase 1).

**화면(`/search`).** 검색창(클라 컴포넌트) → 결과를 **흐름 / 사건** 그룹으로. 흐름 히트는 상태 배지, 사건 히트는 날짜 + **출처 ↗** 외부링크. 모든 히트 클릭 → 해당 `/current/{id}`.

---

## 3. Phase 0 / Phase 1 요약

| | Phase 0 (지금) | Phase 1 |
|---|---|---|
| Following 저장 | localStorage | `/v1/watch*` + 인증 |
| Following 알림 | in-app 변화 배지 | 상태확정 전환 시 푸시 |
| Search 대상 | current + grounded event | + article(정본) |
| Search 방식 | ILIKE | tsvector + BGE-M3 + RRF |
| 페이지네이션 | 없음(소규모) | 커서 |

## 4. 구현 매핑

- 백엔드: `api/repo.py::search()`, `api/main.py GET /v1/search`.
- 타입: `shared/src/types.ts::SearchHit`.
- 클라: `web/app/following/page.tsx`, `web/app/search/page.tsx`, `web/components/TabBar.tsx`(탭 활성), `web/lib/api.ts::searchHits()`.
- 데이터: `scripts/synthesize_timeline.py`가 채운 grounded event가 검색 코퍼스를 풍부하게 함.
