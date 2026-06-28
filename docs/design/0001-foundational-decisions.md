# 0001 — 기반 설계 결정

> **목적:** Meridian Phase 0 착수에 필요한 기반(blocker) 결정을 ADR로 확정한다. 본 문서의 값은 `canon`과 동일하며, 하위 설계 문서는 이를 재발명 없이 그대로 따른다.
> **적용 범위:** Phase 0(geopolitics 1버티컬·수동 current ~10·8주 백필)에 구속력. Phase 1(2버티컬·자동화)·Phase 2(자동 split/merge·확장)는 상위 호환으로 승계한다.
> **상태:** Accepted (2026-06-28).

## 해소하는 스펙 내부 모순(요약)
- **'GDELT only'(§8 Phase 0) vs 본문 필요(§4 embed·§5.3 synthesis):** GDELT는 디스커버리/신호로 한정하고 본문은 화이트리스트 자체 크롤링으로 확보 → ADR-1.
- **상태 3종(§3/§6) vs 'steady'(Appendix China):** `steady`를 정식 4번째 상태로 승격 → ADR-3.
- **6색(§3) vs 10~15 currents(§1):** colorKey 팔레트를 12(+예비 3) 색 레지스트리로 확장 → ADR-11.
- **arc 번호 마커(§2.2) ↔ timeline 노드:** `arc[].marker`(1..5)=`timeline[].node`(1..5)+공유 `eventId`로 결정적 매핑 → ADR-12.

---

## ADR-1 — 본문(body) 확보 전략
**맥락.** Phase 0은 "GDELT only"였으나, 임베딩 대상(title+lede)과 LLM 합성은 실제 본문을 요구한다. GDELT는 본문 전문을 주지 않는다.
**결정.** GDELT는 **디스커버리/신호 레이어**(이벤트·tone·geo)로만 사용한다. 본문은 **신뢰 outlet 도메인 화이트리스트(300~500, `source_registry.is_whitelisted`) 한정 자체 크롤링 + trafilatura/readability 추출**로 확보한다. 추출 실패 기사는 **title+lede로 degrade**(`body_extracted=false`, `body=null`). 라이선스 미확보 소스는 `license_tier='crawl_ttl'`로 본문에 `purge_after` 설정 후 **TTL 폐기**, `metadata_only`는 본문 미저장.
**근거.** 신호의 폭(GDELT)과 텍스트 품질(소량·고신뢰 크롤)을 분리해 양쪽 강점을 취하고, 라이선스 리스크는 TTL·tier로 봉인한다.
**결과.** `source_registry`에 tier/license_tier/body_ttl 필요; 크롤러는 SSRF 가드(ADR-13) 필수; degrade 경로가 임베딩·합성 양쪽에서 정상 동작해야 함.
**대안·기각.** (a) 순수 GDELT only — 본문 없음으로 임베딩/합성 불가, 기각. (b) 전 소스 무차별 크롤 — 라이선스·노이즈·SSRF 리스크 과대, 기각. (c) 라이선스 API 전량 구매 — Phase 0 비용·리드타임 과대, 기각.

## ADR-2 — 임베딩 모델·차원·거리척도
**맥락.** 교차언어 군집이 핵심인데 번역 품질·지연이 임베딩 정합성을 해친다.
**결정.** **BGE-M3(`bge-m3@v1.5`, 1024d)**로 **원문 언어 직접 임베딩**(번역 후 임베딩 금지). 대상=title+lede. `article.embedding_version` 컬럼 필수. 저장=**pgvector vector(1024)**, **HNSW**, **cosine**.
**근거.** BGE-M3는 100+ 언어 단일 공간·8192토큰 컨텍스트로 교차언어 검색/군집에 강하다. 번역 단계 제거로 지연·오류전파 차단. multilingual-e5-large 대비 긴 컨텍스트·dense 검색 성능에서 우위라 default 채택(둘 다 1024d라 차원 호환).
**결과.** 모델 교체 시 전량 재임베딩 필요 → `embedding_version`으로 코호트 분리·점진 재색인.
**대안·기각.** (a) 번역→영어 단일언어 임베딩 — 번역 비용·뉘앙스 손실, 기각. (b) OpenAI/closed 임베딩 — 벤더 종속·버전 핀 곤란, 기각. (c) e5-large default — 동급이나 긴 컨텍스트 약점으로 보조 후보로만.

## ADR-3 — 상태 집합: steady 정식화
**맥락.** §3/§6은 rising/peaking/cooling 3종, Appendix는 China에 'steady'를 사용 — 모순.
**결정.** `momentum_state = {rising, peaking, cooling, steady}` 4종 확정. steady=중립 배지(`#9BA3AF`+`ti-minus`), '극적 사건 없이 베이스라인 부근 지속' 의미(제품의 '꾸준한 누적' 내러티브와 정합).
**근거.** 매 current가 방향을 가져야 하나, '평탄·중립'을 cooling으로 오표기하면 신뢰가 깨진다. 중립 상태가 분류기·UI 양쪽에서 명시적이어야 한다.
**결과.** 분류기·`momentum_point.state`·`current_view.state`·배지 인코딩 모두 4상태 수용. 색 단독 금지(아이콘+라벨).
**대안·기각.** 3상태 유지 — Appendix 모순·중립 표현 불가, 기각.

## ADR-4 — 모멘텀 신호·정규화·상태 분리
**맥락.** 단순 볼륨 급증은 일회성 스파이크에 속는다. 또 '순위'와 '상태'를 한 점수로 묶으면 둘 다 왜곡된다.
**결정.** 4신호: `volume`=7일 EMA, `persistence_days`=robust baseline(median) 초과 연속일수(1~2일 결손 허용 후 리셋), `spread`=신디케이션 접은 outlet/country 다양성, `accel_d1/d2`=7일/14일 도함수. **랭킹 score = 정규화 가중합(accel .30 / persist .30 / volume .25 / spread .15)**. 정규화=흐름내 `log1p(volume)`+robust z(60~90일 median/MAD)→흐름간·버티컬간 재표준화. **랭킹점수 ≠ 상태신호**(state는 accel 형태 분류기로 별도). 상태 임계 `tau_state=k*MAD`(k=1.0) 흐름별 적응, **hysteresis**(진입/이탈 dead-band 0.7배, 2일 연속 확정).
**근거.** 다신호·robust 통계로 스파이크 내성을 얻고, 순위/상태 분리로 "1위지만 cooling" 같은 사실을 표현한다. MAD 비례 적응 임계가 흐름별 스케일 차를 흡수, hysteresis가 배지 플리커를 막는다.
**결과.** `momentum_point`에 baseline_median/mad·tau_state·score·state 동시 저장(투명성·재현성).
**대안·기각.** (a) 볼륨 단일 z-score — 스파이크 취약, 기각. (b) 순위=상태 동일 점수 — 표현력 손실, 기각. (c) 고정 전역 임계 — 흐름별 스케일 불일치, 기각.

## ADR-5 — 서빙: REST + 뷰별 BFF
**맥락.** §7은 REST/GraphQL을 미결로 남김. 3개 뷰는 형태가 고정적이고 캐시 친화적이다.
**결정.** **REST + 뷰별 BFF**. `GET /v1/board`, `GET /v1/currents/{id}`, `GET /v1/digests/{issue}`, `GET /v1/search`. board는 단일 `BoardView` 1콜이며 **streamgraph share를 서버에서 정규화**. **ETag/HTTP 캐시 + ISR(180s, 120~300)**, 응답에 **`asOf`** 노출. **GraphQL 불채택**.
**근거.** 뷰가 소수·안정적이라 BFF가 N+1·오버페치를 제거하고 CDN/ISR 캐시가 단순하다. GraphQL의 유연성은 이득보다 캐시·스키마 운영비가 크다.
**결과.** 클라는 차트 share 계산 안 함(서버 권위). 신선도는 `asOf`로 사용자에 노출.
**대안·기각.** (a) GraphQL — 캐시·보안 표면 복잡, 기각. (b) 클라 정규화 — 디바이스간 불일치·로직 중복, 기각.

## ADR-6 — 클러스터링·current ID 안정성
**맥락.** 진짜 어려움은 정적 분류가 아니라 **시간에 따른 정체성**(split/merge/dormant)이다. digest의 주간 비교가 ID 안정성에 의존한다.
**결정.** 온라인 **leader-follower**(HNSW top-k=20 → cosine τ=0.84 컷, centroid EMA α=0.2, 14일 윈도 만료). **Phase 1 current ID 안정성 = 하향식 택소노미 + append-only 배정으로 구조적 불변(매주 재군집 금지)**. split/merge/dormant는 **명시 이벤트 로그**(`current_lifecycle_event`). Phase 2에서 Jaccard-Hungarian 자동 발견.
**근거.** 매주 재군집은 ID 흔들림→digest 신뢰 붕괴. 큐레이션 택소노미에 append-only로 붙이면 ID가 구조적으로 불변, 변동은 명시 이벤트로만 기록되어 감사 가능.
**결과.** current 생성/분기/소멸은 사람·이벤트로그를 거침. 이벤트는 14일 후 만료(centroid 신선도 유지).
**대안·기각.** (a) 매주 배치 재군집 — ID 불안정, 기각. (b) 순수 자동 발견 Phase 0 도입 — 정확도 미검증, 기각.

## ADR-7 — 사전 dedup
**맥락.** 와이어/신디케이션 재게재가 volume·임베딩을 부풀린다.
**결정.** **canonical URL 정규화 → 본문 64-bit SimHash near-dup(Hamming ≤ 3) 군집 → 군집당 정본 1건만 임베딩**, 나머지는 `canonical_article_id`로 연결·outlet/country 멤버십만 보존(**spread엔 반영, volume=1**).
**근거.** 정본만 임베딩해 ANN 노이즈·비용을 줄이고, 멤버십은 보존해 'spread(도달 폭)'를 정확히 센다.
**결과.** `article.is_canonical/canonical_article_id/simhash` 필요; volume은 정본수, spread는 멤버수 기준.
**대안·기각.** URL만으로 dedup — 동일 본문 다른 URL 누락, 기각. 전량 임베딩 후 dedup — 비용·왜곡, 기각.

## ADR-8 — LLM 합성·인용 하드바인딩
**맥락.** 요약이 편향되거나 인용이 환각이면 신뢰가 붕괴한다(§5.3).
**결정.** current당 코퍼스=이벤트당 대표 1~2건, 본문 2,500토큰 트렁케이션, current당 ≤60k토큰 캡, **prefix 고정으로 prompt caching**. brief/timeline은 **Citations API로 인용을 소스 char span에 하드바인딩**. 발행 전 **verifier**가 인용 스팬 밖 고유명사·수치 스팟체크. 모델 기본 **`claude-sonnet-4-6`**, 최난도 **`claude-opus-4-8`**(현행 ID 확인 완료).
**근거.** 구조적·근거기반 생성만 허용하고 인용을 스팬에 묶으면 환각 인용이 원천 차단된다. prefix 캐싱으로 비용·지연 절감.
**결과.** 인용은 `{outlet,url,charStart,charEnd}`로 timeline에 저장; verifier 실패 시 high-risk fail-closed(ADR-10).
**대안·기각.** 자유 생성 — 편향·환각, 기각. 인용 사후 매칭 — 환각 인용 잔존, 기각.

## ADR-9 — coverage 'How it's covered'
**맥락.** 'opinion이 아닌 실제 분포'여야 하며 정치성향 라벨은 신뢰를 깬다.
**결정.** 버티컬별 축 차등, **검증가능 메타데이터(region_block/outlet_type) 결정적 룩업 1순위**(LLM 프레이밍 보조). **정치성향 라벨 회피**(`source_registry.leaning`은 내부 분석 전용·미노출). outlet-unique + 신디케이션 접기. **min-n(5) 미달 막대 숨김**. 버킷 정의는 `current.coverage_config`, 산출은 `current_view.coverage`.
**근거.** 결정적 메타데이터가 재현성·중립성을 보장. 성향 라벨은 주관·논쟁 유발이라 배제.
**결과.** coverage는 잠금 필드(에디터 수정 불가, ADR-10).
**대안·기각.** LLM 성향 추정 — 환각·편향, 기각.

## ADR-10 — 휴먼 게이트
**맥락.** 톱 10~15만 검수해 품질·확장을 동시에 얻는다.
**결정.** **Draft/Published 2-store + last-known-good 노출**. 필드별 권한: `name`=후보택일(자유입력 2차 승인), `brief`/`timeline`=인라인 교정, `coverage`=잠금, `color_key`=레지스트리 잠금. **high-risk(name/brief/timeline/coverage) fail-closed**(검증·verifier 실패 시 발행 차단), **low-risk(색·정렬) fail-open**(last-known-good 서빙). SLA·롤백·긴급 unpublish·**append-only 감사로그**(`editorial_audit`).
**근거.** 사실성 필드는 막고, 미용성 필드는 가용성을 우선해 운영 마찰을 줄인다. 감사로그로 사후 추적성 확보.
**결과.** 발행 전 verifier 게이트 필수; published는 항상 직전 정상본 보존.
**대안·기각.** 전 필드 자유편집 — 사실 오염, 기각. 단일 store — 롤백 불가, 기각.

## ADR-11 — 클라이언트·차트·팔레트
**맥락.** §3은 6색이나 §1은 10~15 currents — 색 부족.
**결정.** **순수 SVG + d3-shape**(SSR·접근성·테스트), 호버 의존 금지·탭타깃 ≥44px, board ISR 120~300s + 폴링 + `asOf`. 다크테마 WCAG 대비·색 단독 인코딩 금지(아이콘+라벨), 차트 스크린리더 **데이터 테이블 대체**. **colorKey 팔레트 12색(+예비 3, 최대 15) `color_registry`**로 확장, current당 hue 동결·중앙 거버넌스 배정(append-only), 모멘텀 의미색 충돌 hue 제외·colorblind/대비 QA 게이트.
**근거.** SVG는 SSR·a11y·테스트가 쉽고 캔버스보다 접근성 우위. 팔레트를 레지스트리화해 10~15 current에 충돌 없이 안정 배정.
**결과.** `current.color_key`는 레지스트리 잠금(ADR-10); 신규 색 추가는 거버넌스 승인.
**대안·기각.** Canvas/WebGL — a11y·SSR 약점, 기각. 6색 재사용 — 충돌·혼동, 기각.

## ADR-12 — 데이터 모델 갭 해소(§6)
**맥락.** §6은 Vertical·embeddingVersion·weekly_rank·SourceRegistry·arc↔timeline·다대다·license/purge·BoardView·coverage 저장 위치가 비어 있다.
**결정.** 개정 데이터 모델 문서(`# 데이터 모델`)로 전량 해소: `Vertical`+`current.vertical_id`, `article.embedding_version`, `weekly_rank` 스냅샷(동결), `current_lifecycle_event`, `arc[].marker`/`timeline[].node`(1..5)+`eventId` 공유, `article_current` 다대다(`is_primary` 보조태그), `source_registry`, `article.source_license_tier/purge_after`+월 파티셔닝, `board_view`(todays_read 포함), `current.coverage_config`/`current_view.coverage`.
**근거.** 각 갭이 특정 제품 기능(digest 비교·교차언어·발행·coverage)의 전제라 데이터 모델에서 결정적으로 못박아야 한다.
**결과.** 하위 schema.sql/TS는 데이터 모델 문서를 단일 진실원으로 삼는다.
**대안·기각.** 코드 레벨 임시 처리 — 일관성·재현성 붕괴, 기각.

## ADR-13 — 보안(cross-cutting, 스펙 누락 보강)
**맥락.** 스펙은 신뢰불가 본문·크롤·에디터 보안을 다루지 않는다.
**결정.** (a) **LLM 프롬프트 인젝션 방지**: 기사 본문은 데이터 채널로만 주입, 명령 무시 가드, 인용은 char span 검증(ADR-8). (b) **크롤 SSRF 가드**: 화이트리스트 도메인만, IP·리다이렉트·사설망·메타데이터 엔드포인트 차단. (c) **에디터 authn/authz**: 필드별 권한 매트릭스 강제, 모든 변이 `editorial_audit` 기록.
**근거.** 신뢰불가 입력이 합성·인프라·발행 경계를 직접 위협하므로 횡단 관심사로 명시한다.
**결과.** 크롤러·합성·에디터 API 전부에 게이트 코드 필요; 보안 회귀 테스트 포함.
**대안·기각.** 사후 대응 — 인젝션/SSRF는 사전 차단만 유효, 기각.

## ADR-14 — Phase 0 범위·Go/No-Go
**맥락.** 컨셉이 실데이터에서 성립하는지 수치로 판정해야 한다.
**결정.** **1버티컬(geopolitics), ~10 수동 큐레이션 current, 8주 백필**. Go/No-Go: 클러스터 purity ≥ 0.80; current ID churn = 0; 상태-인간 일치 ≥ 70%; coverage 결정적 룩업 ≥ 95%; 인용 유효성 100%·verifier 환각 < 5%; board p95 staleness ≤ 5분; 에디터 10 current 검수 < 30분/일.
**근거.** 정량 게이트가 없으면 '느낌'으로 Phase 1에 진입한다. 각 지표는 ADR-4/6/8/9/10/5에 직접 매핑.
**결과.** 미달 지표는 해당 ADR 재튜닝 트리거.
**대안·기각.** 정성 평가만 — 의사결정 불가, 기각.

---

## 0007 — 상태배지색과 current hue 충돌 방지 (color governance)

- **맥락:** 스펙 §3은 momentum 상태색(amber/coral/steel)과 current hue(ai-governance/amber, cost-of-living/coral, middle-east/steel)에 **동일 헥스**를 부여 — "색으로 레이어를 안다"는 원칙 자체를 훼손.
- **결정:** 상태배지 4색을 `color_registry`에 예약(is_reserved)하고 current 배정 풀에서 제외. 충돌 4개 current를 재배정 **확정**: ai-governance→orchid `#C46BD8`, cost-of-living→rose `#E86A8E`, energy→lime `#9CCB3B`, middle-east→indigo `#5C6BC0`(china/climate 유지). 신규 배정 시에만 ΔE·WCAG·colorblind QA 게이트 적용. [[CANON]] R11.
- **결과:** 활성 12색(+예비 3) 팔레트 + 배정 거버넌스 필요. 디자인 후속 작업 1건 생성.
- **대안 기각:** "아이콘+라벨만으로 구분" — 작은 배지에서 색 혼동 잔존, 원칙 약화로 기각.

## 0008 — license_tier 단일 ENUM 통일

- **맥락:** 본문 저장 라이선스 등급이 문서마다 source_tier 재사용/`{full,snippet,metadata}`/`noindex`로 제각각.
- **결정:** 전용 `license_tier = {full, snippet, metadata}`로 통일, source_registry·article 양쪽에 적용. 합성 필터 `IN ('full','snippet')`. [[CANON]] R5, [[data-model]].
- **결과:** 본문 보존·grounding 코퍼스 적격성이 단일 기준으로 결정.

## 0009 — 표시언어(로케일) 경계와 발행 뷰 lang 차원

- **맥락:** MVP는 "English first then Korean"인데 API/클라 경계에 로케일 선택·발행 객체의 언어 차원이 없었음(국제화 갭).
- **결정:** API `?lang=`/Accept-Language + 응답 `lang`. 발행 뷰 PK에 `lang` 추가(Phase 0 'en'). [[CANON]] R12.
- **결과:** Phase 1 한국어가 마이그레이션이 아닌 데이터 추가로 가능.

## 0010 — arc 표시 스케일(정규화 발행값)

- **맥락:** 생산자(momentum)는 arc=raw EMA, 소비자(api/client)는 0..1 정규화로 불일치.
- **결정:** momentum_point.volume=raw 유지, 발행 current_view.arc[].value=서버 정규화 [0,1]. [[CANON]] R4.
- **결과:** sparkline·attention bar·arc가 동일 스케일로 일관.
