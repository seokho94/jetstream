# Jetstream — 설계 문서 (Phase 0)

`docs/jetstream-spec.md`(제품·엔지니어링 브리프)를 **착수 가능한 설계**로 구체화한 문서 세트입니다. 갭 분석 → 권장 방향 확정 → 상호 일관성 검수(2라운드)를 거쳐 작성됐습니다.

## 권위 순서 (충돌 시)

1. **[CANON.md](CANON.md)** — 확정값(이름·타입·상수)의 단일 진실원. 특히 **§14 RESOLUTIONS**가 모든 문서에 우선합니다. 각 상세 문서 상단의 `⚠️ 검수 반영(v2)` 배너가 어느 R항목으로 갱신됐는지 가리킵니다.
2. **[0001-foundational-decisions.md](0001-foundational-decisions.md)** — 기반(blocker) 결정의 ADR 기록(맥락/결정/근거/대안).
3. 아래 상세 설계 문서들.

상위 스펙 `../jetstream-spec.md`와 충돌하면 본 세트가 이깁니다(스펙 내부 모순 — `steady` 상태, "GDELT only" vs 본문, 6색 vs 10~15, arc↔timeline — 을 의도적으로 해소했기 때문).

## 읽는 순서

| 순서 | 문서 | 한 줄 |
|---|---|---|
| 1 | [CANON.md](CANON.md) | 확정값·상수·RESOLUTIONS(§14). 먼저 읽을 것 |
| 2 | [0001-foundational-decisions.md](0001-foundational-decisions.md) | 기반 결정 ADR(0001–0010) |
| 3 | [data-model.md](data-model.md) | TS 인터페이스 + Postgres DDL(스키마 정본) |
| 4 | [ingestion-and-clustering.md](ingestion-and-clustering.md) | 본문 확보·dedup·정규화·온라인 클러스터링·ID 안정성 |
| 5 | [momentum-engine.md](momentum-engine.md) | 4신호 산식·정규화·상태분류(4상태)·랭킹·arc 파생 |
| 6 | [synthesis-and-trust.md](synthesis-and-trust.md) | LLM 합성·grounding(Citations)·coverage·중립성·휴먼 게이트 |
| 7 | [api-contract.md](api-contract.md) | REST 엔드포인트·BoardView/CurrentView/Digest 페이로드·캐싱 |
| 8 | [client-architecture.md](client-architecture.md) | SVG 차트·접근성·colorKey 거버넌스·온보딩·상태/페칭 |
| 9 | [phase-0-plan.md](phase-0-plan.md) | 백로그·리포 스캐폴드·go/no-go 지표·리스크 |

## 핵심 확정 (요약)

- **임베딩:** BGE-M3, `vector(1024)`, cosine, 원문 직접 임베딩, `embedding_version` 컬럼.
- **상태:** `{rising, peaking, cooling, steady}` 4상태(색 단독 인코딩 금지, 아이콘+라벨).
- **모멘텀:** score = `0.30 z_accel + 0.30 z_persist + 0.25 z_vol + 0.15 z_spread`, 흐름내 robust z + 버티컬간 재표준화. 랭킹점수 ≠ 상태신호.
- **클러스터링:** 온라인 leader-follower(τ≈0.84), current ID는 **하향식 택소노미 + append-only**로 구조적 불변(digest 주간 비교 보존).
- **서빙:** REST + 뷰별 BFF, board 단일 `BoardView` 1콜(share 서버 정규화), ETag/ISR + `asOf`.
- **합성:** Citations API로 인용을 소스 char span에 하드바인딩 + 발행 전 verifier. 기본 `claude-sonnet-4-6`/최난도 `claude-opus-4-8`.
- **게이트:** Draft/Published 2-store + last-known-good, 필드별 편집권한, high-risk fail-closed.

## 사인오프 대기 / 후속 결정

- **🎨 색상(R11) — ✅ 확정:** 상태배지 4색·브랜드 틸·헬퍼·Other를 예약하고, 충돌 current 4색을 재배정 확정(ai-governance `#C46BD8` · cost-of-living `#E86A8E` · energy `#9CCB3B` · middle-east `#5C6BC0`). 시드: `data-model.md` `color_registry`, 시각 확인: `color-swatches.html`. 신규 current 배정 시에만 QA 게이트.
- **벤더·라이선스:** 뉴스 API 벤더 선정과 본문 저장·재배포 라이선스 계약(체크리스트는 ingestion 문서 §1.3).
- **본문 바디 레벨 정합:** 본 라운드에서 일부 문서의 잔여 medium/low 불일치는 **CANON §14 + 상단 배너**로 권위 해소했습니다. 문서 본문 자체의 전면 재작성은 후속 작업으로 남겨둘 수 있습니다(현재는 CANON이 정본).
