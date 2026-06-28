# Ingestion & Clustering — Meridian Data Pipeline

> **⚠️ 검수 반영(v2):** [CANON](CANON.md) **§14**로 갱신 — 충돌 시 §14 최우선. 적용: **R5**(전용 ENUM `license_tier {full,snippet,metadata}`를 `source_registry`·`article` 양쪽에; `source_tier` 재사용 금지, `noindex`→`metadata`).

> **목적 (1줄):** 전 세계 raw 뉴스를 vertical-scoped·dedup·정규화·임베딩한 `article` 행으로 만들고, 온라인 leader-follower로 `event`를 만든 뒤 안정 ID `current`에 append-only로 배정하는 **수집~클러스터링 단계**(spec §4 stage 1–3, §5.1)의 운용 명세.
>
> **적용 범위:**
> - **Phase 0** — vertical 1개(`geopolitics`), 수동 큐레이션 current ~10개, 8주 백필. cron 오케스트레이션. 본 문서 전 절 구속.
> - **Phase 1** — vertical 2개(+`technology`), 온라인 클러스터링 자동화, Dagster/Prefect 오케스트레이션, 하향식 택소노미 + append-only 배정.
> - **Phase 2** — 다소스/다언어 확장, split/merge 자동 발견(Jaccard-Hungarian). canon 상위 호환(컬럼·임계 추가만, 의미 변경 금지).
>
> **canon이 이긴다.** 아래의 모든 상수·이름·임계는 canon에서 그대로 가져왔으며 재발명하지 않는다.

---

## 0. 파이프라인 토폴로지 (이 문서가 담당하는 구간)

```
[1 Collect] GDELT DOC2.0/GKG2.1 · News API · RSS
      │  (raw_doc, source_domain, gdelt fields)
      ▼
[2a Scope]  whitelist AND language AND GKG theme  ──▶ drop (스코프 밖)
      ▼
[2b Dedup]  canonical_url 정규화 → SimHash near-dup → 정본 선택
      ▼
[2c Normalize] body 확보(crawl+trafilatura, degrade) · langdetect · 번역(title/lede) · NER/event · embed(원문)
      │  upsert article (url-hash 멱등)
      ▼
[3a Event]  leader-follower (HNSW top-20 → cosine ≥ TAU_CLUSTER) · centroid EMA · 14d 만료
      ▼
[3b Current] event → current append-only 배정 (택소노미 seed) · lifecycle 로그
      ▼   (이후 §5.2 momentum, §5.3 synthesis — 본 문서 범위 밖)
```

수집~클러스터링은 **idempotent·append-only**가 원칙이다: 재실행/백필이 같은 입력에 대해 같은 행을 만들어야 하고(§5 멱등 upsert), current ID는 절대 재발급하지 않는다(§13 churn=0).

---

## 1. 소스 — 제품 선택·본문 확보·라이선스

### 1.1 GDELT 제품 선택

| 제품 | 용도 | Meridian에서의 역할 | 채택 |
|------|------|---------------------|------|
| **GDELT DOC 2.0 API** | 도메인/언어/시간 필터 기사 검색, `timespan`/`sourcecountry`/`domain` 파라미터 | Phase 0 1차 소스. URL·published_at·언어·도메인·tone 시드 확보 | **채택(Phase 0 primary)** |
| **GDELT GKG 2.1** (`*.gkg.csv` 15분 파일) | 테마(`V2THEMES`/`THEMES`), 엔티티(`V2PERSONS`/`V2ORGANIZATIONS`), 지역(`V2LOCATIONS`), `V2TONE` | **버티컬 theme 필터의 권위 소스** + countries/tone 보강. theme = vertical 스코핑 AND 조건 | **채택(theme/geo/tone)** |
| GDELT Events 2.0 (CAMEO) | actor-action-actor 이벤트 코딩 | Phase 0 미사용(CAMEO 입도가 macro current에 과하게 세분). Phase 2 event 보강 후보 | 보류 |

**근거 1줄:** DOC 2.0은 URL 발견·필터에, GKG 2.1은 theme/geo/tone 메타에 강하다 → 둘을 join(같은 `DocumentIdentifier`=URL)해 `article`의 `countries`/`tone`/theme를 채운다. Events(CAMEO)는 입도가 너무 세분이라 macro current 단위와 맞지 않아 Phase 0 제외.

**GKG 2.1 → article 매핑:**

```
V2THEMES         → vertical theme 필터 (§2.1) + (선택) event 보조 신호
V2LOCATIONS      → article.countries text[]   (ADM1/country FIPS → ISO-3166 변환)
V2TONE[0]        → article.tone numeric        (canon: article.tone)
V2PERSONS/ORGS   → 엔티티 추출 시드 (§4.3)
DocumentIdentifier → canonical_url 정규화 입력 (§3.1)
```

GKG 15분 파일 수집은 `lastupdate` 커서(§5.1)로 폴링한다. DOC 2.0과 GKG는 **URL을 키로 left-join**하되, GKG에만 있는 URL도 스코프 통과 시 수집한다(GKG가 더 넓은 theme 커버리지).

### 1.2 본문(body) 확보 — whitelist 크롤링 + trafilatura + degrade

GDELT/뉴스API는 **URL과 메타만** 주고 전문은 주지 않는다. canon 임베딩 대상은 `title + lede`이고 lede = 본문 첫 1~2문장이므로 **본문 추출이 임베딩 품질의 전제**다.

추출 파이프라인:

```
fetch(canonical_url)            # §10 SSRF 가드 통과한 요청만
  → trafilatura.extract(html)  # 메인 본문 + 메타(date/title) 추출
  → body, lede(first 1–2 sent), body_extracted=true
```

**Degrade 사다리(canon: `lede` 추출 실패 시 title 단독 임베딩):**

| 단계 | 조건 | 동작 | `body_extracted` | 임베딩 대상 |
|------|------|------|------------------|-------------|
| L0 | trafilatura 본문 OK | body 저장, lede = 첫 1~2문장 | `true` | `title + lede` |
| L1 | 본문 추출 실패, GDELT/RSS description 존재 | description을 lede로 사용 | `false` | `title + lede(desc)` |
| L2 | 본문·description 모두 없음 | lede NULL | `false` | **`title` 단독** (canon §1) |
| L3 | fetch 자체 실패(차단/타임아웃/SSRF 거부) | body NULL, `is_canonical`이면 title로 L2 임베딩 | `false` | `title` 단독 |

`body`는 nullable, `body_extracted boolean`로 degrade 추적. **본문은 데이터 채널로만** 흐르고 LLM 명령 채널로 들어가지 않는다(§12 인젝션 방지; 본 문서 범위 밖 synthesis에서 강제).

크롤링 정책: `source_registry.body_ttl`(도메인별 캐시 TTL) 준수, 도메인당 동시성 ≤ 2, robots.txt 존중, 지수 백오프(§5.4). 본문 보존기간은 `article.purge_after`(라이선스 tier에 따른 TTL)로 제어.

### 1.3 News API / RSS의 역할

| 소스 | 역할 | Phase |
|------|------|-------|
| **GDELT** | 1차 발견 — 글로벌·다언어·theme/geo 메타 | 0+ |
| **News API(라이선스 wire)** (예: AP/Reuters/AFP feed, GNews/NewsAPI.org 등) | wire 원문·신뢰 outlet 보강, GDELT 누락 보완, 라이선스된 본문 접근 | 1+ |
| **RSS 크롤러** | long-tail outlet·전문지 커버리지, whitelist 도메인 직접 폴링 | 1+ |

세 소스 모두 동일 `article` 스키마로 정규화되며 **dedup(§3)에서 합류**한다 — 같은 기사가 GDELT·News API·RSS 3경로로 들어와도 canonical_url + SimHash로 1정본으로 접힌다.

**라이선스 체크리스트(소스 온보딩 게이트, `source_registry.license_tier`에 기록):**

- [ ] 본문 **저장** 허용 범위(전문 저장 vs. 발췌만 vs. URL/메타만) — `license_tier`로 인코딩.
- [ ] **재배포/표시** 허용(brief/timeline에 인용 표시 가능한가) — canon §9 Citations는 char span 인용이므로 발췌 인용 권리 필수.
- [ ] **TTL/보존** 제약 → `source_registry.body_ttl` + `article.purge_after` 매핑.
- [ ] **rate limit / attribution** 의무(outlet_name 표기) — `source_registry.outlet_name`.
- [ ] robots.txt / ToS 크롤 허용 여부.
- [ ] 비용·쿼터(일일 콜 상한 → §2 cost 모델 반영).

`license_tier`별 본문 처리:

```
license_tier = 'full'      → body 저장·char-span 인용 가능, purge_after = body_ttl
             = 'snippet'   → lede만 저장(≤2문장), 인용은 snippet 범위 내
             = 'metadata'  → body NULL, title만 임베딩(L2), 링크-아웃만
```

---

## 2. 버티컬 스코핑 필터 · 일일 상한 · cost 모델

### 2.1 스코핑 필터 (AND 결합)

기사가 vertical에 들어오려면 **세 조건 모두** 충족(canon coverage_config 활용):

```sql
-- 의사 술어: vertical 'geopolitics' 스코핑
accept(article) :=
       source_registry.is_whitelisted = true          -- (1) 도메인 화이트리스트
   AND article.language = ANY(vertical_langs)          -- (2) 언어
   AND article.gkg_themes && vertical_theme_set         -- (3) GKG theme 교집합 ≠ ∅
```

`current.coverage_config jsonb`에 vertical별 버킷 정의를 둔다(canon §10):

```json
{
  "vertical": "geopolitics",
  "langs": ["en"],                    // Phase 0 en only; Phase 1 +ko
  "themes_any": [                     // GKG V2THEMES — 하나라도 매칭 시 통과
    "WB_2467_TERRORISM", "MILITARY", "ARMEDCONFLICT",
    "GENERAL_GOVERNMENT", "DIPLOMACY", "WB_2670_JOBS_VS_DIPLOMACY",
    "ELECTION", "SANCTIONS"
  ],
  "domain_whitelist_ref": "source_registry.is_whitelisted"
}
```

**근거 1줄:** theme를 AND로 강제하면(단순 도메인·언어만이 아니라) 화이트리스트 outlet의 스포츠/연예 기사가 geopolitics current를 오염시키는 것을 GKG 결정적 룩업으로 차단 → §13 coverage 결정적 룩업 ≥95% 목표에 부합.

Phase 0은 langs=`["en"]`(임베딩은 어차피 원문, 번역은 표시용). 비-en 기사는 스코프에서 제외하되 row는 `dropped_scope` 사유로 감사 로깅(필터 튜닝용).

### 2.2 일일 상한 (cost·noise 제어)

| 상한 | Phase 0 기본값 | 근거 |
|------|----------------|------|
| `INGEST_DAILY_CAP` (vertical당 raw 수집) | 20,000 docs/day | GDELT geopolitics-en 일평균 처리 가능량, 초과 시 tone 극단·tier 낮은 outlet부터 샘플링 |
| `EMBED_DAILY_CAP` (정본만 임베딩) | 6,000 articles/day | dedup 후 정본 비율 ~30% 가정 |
| `CRAWL_DAILY_CAP` (본문 fetch) | 6,000 fetch/day | 정본만 크롤(near-dup은 fetch 안 함) |
| 도메인당 fetch/시간 | 120 | robots/예의 |

상한 초과 시 **drop이 아니라 우선순위 큐**: `source_tier` 높은 outlet + theme 강매칭 우선. 잔여는 다음 윈도로 이월(watermark는 진행, 미처리분은 DLQ-defer로 표시).

### 2.3 1쪽 cost 모델

**단가 가정(Phase 0, USD):**

```
EMBED_UNIT   = $0.00002 / 1K tokens   (self-host BGE-M3 상각가 또는 hosted 환산)
SYNTH_IN     = $3.00    / 1M tokens    (claude-sonnet-4-6 input, prompt-cached 할인 전)
SYNTH_OUT    = $15.00   / 1M tokens    (output)
STORAGE_PG   = $0.30    / GB-month     (Postgres+pgvector)
AVG_EMB_TOK  = 120 tokens / article    (title+lede)
VEC_BYTES    = 1024 dim × 4B = 4096 B / vector
```

**일일 임베딩 비용:**
```
embed_cost/day = canonical_articles/day × AVG_EMB_TOK × EMBED_UNIT
              = 6,000 × 120 × ($0.00002/1000)
              = 6,000 × 120 × 0.00000002
              ≈ $0.0144 / day   (≈ $0.43 / month)
```
임베딩은 정본(`is_canonical=true`)에만 — near-dup은 0 토큰(canon §5). 사실상 무시 가능; 비용 지배항은 synthesis다.

**스토리지(월):**
```
vectors  = 6,000/day × 30 × 4096 B ≈ 0.69 GB → $0.21/mo
+ body 텍스트(평균 4KB, full-tier만 ~30%) ≈ 6,000×30×0.3×4KB ≈ 0.22 GB → $0.07/mo
+ HNSW 인덱스 오버헤드(~1.5×) ≈ $0.31
≈ $0.6/mo  (purge_after로 상한)
```

**Synthesis 호출(§9, current당, 본 문서 외이지만 cost 총합용):**
```
per_current_in  ≤ LLM_CURRENT_TOK_CAP = 60,000 tok
weekly cost ≈ currents(10) × (60k×SYNTH_IN + ~4k×SYNTH_OUT)
            = 10 × (0.060×$3 + 0.004×$15)
            = 10 × ($0.18 + $0.06) = $2.40 / synthesis-run
prompt caching(prefix 고정)으로 input 실효 ~−50% → ≈ $1.5/run
```

**요약:** Phase 0 수집~클러스터링의 변동비는 **임베딩+스토리지 합 월 $1 미만**, 파이프라인 총비용은 synthesis가 지배(주당 ~$2.4). 즉 일일 상한의 목적은 비용이 아니라 **noise·crawl 부하 제어**다.

---

## 3. 사전 dedup (canon §5)

### 3.1 canonical URL 정규화 규칙 → `article.canonical_url`

순서(결정적):

1. scheme 소문자, **host 소문자**, 기본 포트 제거(`:80`/`:443`).
2. `www.` 접두 제거(단, `source_registry`에 등록된 정확 host는 보존).
3. **fragment(`#…`) 제거**.
4. **추적 파라미터 제거**: `utm_*`, `gclid`, `fbclid`, `mc_cid`, `mc_eid`, `igshid`, `ref`, `ref_src`, `spm`, `cmpid`.
5. **AMP 해소**: `/amp/`·`?amp=1`·`amp.`/`.amp` suffix 제거 → canonical 형태로 환원, `<link rel="canonical">`가 있으면 그 값 우선.
6. 잔여 query **키 정렬**(알파벳), 빈 값 키 제거.
7. trailing slash 정규화(path가 `/`만이면 제거, 그 외 보존).

```python
def canonicalize(url: str) -> str:
    u = urlsplit(url.strip())
    host = u.hostname.lower().removeprefix("www.")
    q = sorted((k, v) for k, v in parse_qsl(u.query)
               if not k.lower().startswith("utm_")
               and k.lower() not in TRACKING_KEYS and v)
    path = resolve_amp(u.path).rstrip("/") or "/"
    return urlunsplit((u.scheme.lower(), host_with_port(host, u.port),
                       path, urlencode(q), ""))   # fragment dropped
```

`url_hash = sha256(canonical_url)` → **멱등 upsert 키**(§5.2)이자 SimHash 전 1차 dedup(정확 중복 즉시 접힘).

### 3.2 SimHash near-dup

- **본문 64-bit SimHash**(canon `SIMHASH_HAMMING_MAX=3`). 토큰 = body의 word 3-gram shingle(본문 없으면 title shingle).
- 새 기사의 simhash와 **같은 dedup 윈도(48h) 내** 기존 정본들을 **Hamming distance ≤ 3**으로 비교 → 군집화.
- 비교 가속: 64bit를 4×16bit 밴드로 쪼개 **밴드별 정확일치 후보만** 거리 계산(LSH), full pairwise 회피.

```sql
ALTER TABLE article ADD COLUMN simhash bigint;   -- 64-bit signed
-- 후보 조회(밴드 인덱스 가정): 같은 윈도·같은 source_domain 무관, 같은 vertical
```

### 3.3 정본 선택 (canonical 1건)

near-dup 군집에서 **정본 1건**을 결정(canon: 정본만 임베딩):

우선순위(첫 결정 규칙에서 멈춤):
1. `source_registry.tier` 높은 outlet(`tier1` > `tier2` > …).
2. `license_tier = 'full'` (인용 권리 있는 본문).
3. `body_extracted = true` (전문 확보).
4. `published_at` **가장 이른** 것(원전/오리지널).
5. tie → `url_hash` 사전순(결정적·재현가능).

```sql
UPDATE article SET is_canonical = (id = chosen_id),
                   canonical_article_id = CASE WHEN id = chosen_id
                                               THEN NULL ELSE chosen_id END
WHERE simhash_cluster_id = :cid;
```

### 3.4 spread / volume 카운팅 규칙 (canon §5 LOCK)

- **임베딩**: 정본 1건만 `vector(1024)` 보유, 나머지는 `embedding = NULL`.
- **volume**(§3 momentum 근거): **정본만 카운트**, near-dup은 **volume=1에 기여 안 함**(신디케이션이 volume을 부풀리지 않음). → `event.article_count` = 정본 수.
- **spread**: near-dup의 **outlet/country 멤버십은 보존**해 spread에 반영. → `event.member_count` = near-dup 포함 멤버 수, `spread_outlets`/`spread_countries`는 멤버 전체의 distinct.

```sql
-- 카운팅 의미 (event 집계 시)
article_count = count(*) FILTER (WHERE is_canonical)                  -- volume 근거
member_count  = count(*)                                              -- spread 근거(near-dup 포함)
spread_outlets   = count(DISTINCT source_domain)                      -- 신디케이션 접은 후
spread_countries = count(DISTINCT unnest(countries))
```

near-dup row는 `(source_domain, country)` 멤버십만 들고 `canonical_article_id`로 정본을 가리킨다 — 본문·임베딩 중복 저장 없음.

---

## 4. 정규화

### 4.1 언어 감지

- `fasttext lid.176` 또는 `cld3`로 `article.language`(ISO-639-1). title+lede 합쳐 감지(짧은 텍스트 robust).
- GDELT가 준 언어가 있으면 1차 채택, 추출 본문과 불일치 시 본문 감지 우선.
- 스코프 언어(§2.1 `langs`) 밖이면 `dropped_scope`.

### 4.2 번역 범위 (canon §1: 임베딩은 원문)

| 텍스트 | 번역? | 저장 | 임베딩 |
|--------|-------|------|--------|
| `title` | **표시용 번역**(target=화면 언어, Phase 0 en) | 원문 title + (선택) 번역 캐시 | — |
| `lede` | 표시용 번역 | 원문 lede | — |
| **임베딩 입력** | **번역 금지** | — | **원문 `title + lede` 직접 임베딩**(BGE-M3 다국어) |
| `body` | 미번역(인용은 원문 char span에서) | 원문 body | — |

**근거 1줄:** BGE-M3는 다국어 정렬 임베딩이라 번역 없이 cross-lingual 클러스터링이 되고, 번역 임베딩은 MT 노이즈를 주입하므로 canon이 원문 임베딩을 LOCK.

### 4.3 엔티티/이벤트 추출

- **엔티티**: GKG `V2PERSONS`/`V2ORGANIZATIONS`/`V2LOCATIONS` 결정적 룩업 1순위(§10 정신). 보강 필요 시 spaCy NER(en) — 단 GKG 우선.
- **countries**: `V2LOCATIONS` → ISO-3166-1 alpha-3 정규화 → `article.countries text[]`.
- **tone**: `V2TONE[0]` → `article.tone numeric`.
- **event 신호**: Phase 0은 GKG theme+엔티티를 보조 신호로만 보관(클러스터링은 임베딩 주도, §6). CAMEO event 코딩은 Phase 2.

### 4.4 임베딩 (canon §1 LOCK — 변형 금지)

```
EMBED_MODEL    = bge-m3
EMBED_REVISION = v1.5
dim            = 1024
distance       = cosine  (vector_cosine_ops)
input          = title + lede   (lede 실패 시 title 단독)
embedding_version = "bge-m3@v1.5"   ("<model>@<revision>")
대상           = is_canonical=true 인 정본만 (그 외 embedding=NULL)
```

```sql
-- canon §6 article 컬럼
embedding         vector(1024),
embedding_version text,            -- 'bge-m3@v1.5'

-- canon §1 인덱스
CREATE INDEX article_embedding_hnsw
  ON article USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
SET hnsw.ef_search = 100;          -- 질의 시
```

`embedding_version`은 **필수 컬럼**: 재처리(§9)·모델 교체 시 어떤 벡터가 어느 모델 산출인지 분리·혼용 방지의 키.

---

## 5. 수집 스케줄링 / 오케스트레이션

### 5.1 GDELT `lastupdate` 오프셋 커서

GDELT는 15분마다 `lastupdate.txt`(최신 파일 URL/타임스탬프)를 갱신한다. 폴링 커서:

```
state: gdelt_cursor { last_lastupdate_ts, last_file_url, offset }
loop (every 15 min, with skew tolerance):
  cur = fetch("http://data.gdeltproject.org/gdeltv2/lastupdate.txt")
  if cur.ts <= state.last_lastupdate_ts:  no-op (아직 새 파일 없음)
  else: process files (state.last .. cur.ts], 빠진 슬롯은 백필 큐로
  checkpoint state.last_lastupdate_ts = cur.ts  # 처리 성공 후에만
```

**오프셋 안전마진**: GKG 파일은 발행 후 수분 지연·재발행될 수 있으므로 커서를 `now - 15min`보다 뒤로 두지 않되, **마지막 2슬롯은 재처리 허용**(멱등 upsert가 중복을 흡수). 누락 슬롯은 watermark gap으로 감지해 백필.

### 5.2 멱등 upsert (url-hash)

```sql
-- article PK는 (id, published_at) 월 RANGE 파티션. 자연키 멱등은 url_hash unique.
CREATE UNIQUE INDEX article_url_hash_uk
  ON article (url_hash, published_at);   -- 파티션 정렬 위해 published_at 포함

INSERT INTO article (id, url_hash, canonical_url, source_domain, language,
                     title, lede, body, body_extracted, published_at, countries, tone, ...)
VALUES (...)
ON CONFLICT (url_hash, published_at) DO UPDATE
  SET title = EXCLUDED.title,
      lede  = EXCLUDED.lede,
      body  = COALESCE(EXCLUDED.body, article.body),   -- degrade 보강만
      body_extracted = article.body_extracted OR EXCLUDED.body_extracted,
      countries = EXCLUDED.countries,
      tone = EXCLUDED.tone
  WHERE article.is_canonical IS NOT FALSE;             -- 정본 결정 후엔 멤버십 변경 금지
```

같은 기사가 3소스로 들어와도 `url_hash`로 1행 보장 → 재실행·백필이 행을 복제하지 않음(idempotent).

### 5.3 watermark 체크포인트

각 스테이지 진행을 watermark로 분리 기록(스테이지간 디커플):

```sql
CREATE TABLE pipeline_watermark (
  stage      text PRIMARY KEY,   -- 'gdelt_ingest','crawl','embed','event_cluster','current_assign'
  vertical_id text,
  watermark  timestamptz,        -- 이 시각 이전 입력은 처리 완료 보장
  cursor     jsonb,              -- {last_lastupdate_ts, file_url, ...}
  updated_at timestamptz default now()
);
```

watermark는 **at-least-once + 멱등**: 크래시 후 watermark부터 재처리해도 upsert가 중복 없이 수렴. board 신선도(§13 p95 ≤5분)는 `embed`/`current_assign` watermark로 측정.

### 5.4 재시도 / 지수 백오프 / DLQ

```
retry: max_attempts=5, base=2s, factor=2, jitter=±20%, cap=120s
       → 2s, 4s, 8s, 16s, 32s(±jitter)
재시도 대상: 5xx, 429, 타임아웃, 일시 네트워크
즉시 DLQ(재시도 안 함): 4xx(429 제외), SSRF 거부, robots 차단, 파싱 불가
```

```sql
CREATE TABLE ingest_dlq (
  id bigserial PRIMARY KEY,
  stage text, payload jsonb, url text, url_hash bytea,
  error_class text,        -- 'http_4xx','ssrf_blocked','parse_fail','rate_limited'
  attempts int, first_failed_at timestamptz, last_failed_at timestamptz,
  next_retry_at timestamptz, resolved_at timestamptz
);
```

DLQ는 일 1회 재구동(재시도 가능 클래스만), 임베딩 상한 초과로 이월된 항목은 `defer`로 분리. DLQ 적체 알람 임계: vertical당 미해결 > 500 또는 24h 초과 항목 존재.

### 5.5 Phase 0 cron → Phase 1 Dagster/Prefect

| | Phase 0 | Phase 1+ |
|--|---------|----------|
| 오케스트레이션 | cron(15분 GDELT, 시간별 crawl, 일별 cluster/momentum) | **Dagster**(asset 그래프) 또는 Prefect(flow) |
| 의존성 | 암묵(스크립트 순서) | 명시 DAG: `ingest → scope → dedup → normalize → embed → event → current` asset 의존 |
| 백필 | 수동 스크립트 | partitioned asset 재실행(동일 코드, §9) |
| 관측 | 로그 | asset 메타·SLA·watermark 센서, DLQ 센서 자동 재구동 |

**근거 1줄:** Phase 0은 단일 vertical·소수 잡이라 cron으로 충분(운영 단순), Phase 1은 스테이지 의존·백필·재처리(embeddingVersion)가 늘어 **asset/lineage 추적이 가능한 Dagster**가 멱등 partition 재실행에 유리.

---

## 6. 온라인 이벤트 클러스터링 (canon §4 LOCK)

### 6.1 leader-follower 알고리즘

새 정본 기사 1건이 임베딩되면:

```
1. q = article.embedding                                   # vector(1024), 원문
2. cand = HNSW top-k(q, k = CLUSTER_TOPK = 20)             # 활성(미만료) event centroid 대상
        ef_search = 100
3. best = argmax cosine_sim(q, event.centroid) over cand
4. if cosine_sim(best) >= TAU_CLUSTER (= 0.84):            # 범위 0.82~0.86
       assign article.event_id = best.id  (follow)
       update centroid (EMA, §6.3)
       event.last_seen = article.published_at
       event.expires_at = last_seen + 14d
   else:
       spawn new event (leader): centroid = q,
       first_seen = last_seen = published_at,
       expires_at = published_at + CLUSTER_WINDOW_DAYS(14)
```

후보는 **활성 event**(`expires_at > now`)의 centroid에 대해서만 검색(만료 event는 신규 배정 대상 아님 → §6.4).

### 6.2 τ 캘리브레이션 (ROC)

`TAU_CLUSTER` 기본 0.84, 허용 범위 0.82~0.86. 캘리브레이션:

1. **라벨셋**: geopolitics 기사쌍 수백 개를 "같은 event/다른 event"로 수동 라벨(§13 purity 샘플과 공유).
2. cosine_sim 분포에 대해 **ROC** — threshold sweep 0.80→0.88.
3. 목표: **precision 우선**(잘못 합치는 비용 > 쪼개는 비용; split은 후속 보정 가능, 잘못된 merge는 current 오염). Youden J 또는 precision≥0.9 지점 선택.
4. 선택값이 [0.82, 0.86] 안이면 채택, 밖이면 0.84로 clamp + 사유 기록.

```
재캘리브레이션 트리거: purity < 0.80(§13) 또는 embeddingVersion 변경(§9)
```

### 6.3 centroid EMA

```
CENTROID_ALPHA = 0.2
centroid_new = normalize( (1 - 0.2) * centroid_old + 0.2 * q )
            = normalize( 0.8 * centroid_old + 0.2 * q )
```

cosine 거리이므로 갱신 후 **L2 정규화**(단위벡터 유지). `event.centroid vector(1024)` 갱신은 follow 시마다. EMA(α=0.2)는 최신 기사에 20% 가중 → drift 추종하되 outlier 1건이 centroid를 흔들지 않음.

### 6.4 윈도 만료

```sql
-- event.expires_at = last_seen + 14d  (CLUSTER_WINDOW_DAYS=14)
-- 만료 event: 신규 기사 배정 대상에서 제외(HNSW 후보 필터)
WHERE event.expires_at > now()

-- 만료 처리(일별): 활성 인덱스에서 제외, current dormant 판정 입력(§8)
UPDATE event SET ... WHERE expires_at <= now();  -- 물리 삭제 아님, 비활성 표시
```

만료된 event는 보존(아카이브)하되 leader-follower 후보군에서 빠진다 → 오래된 주제가 새 기사를 흡수해 centroid가 표류하는 것을 방지. 같은 주제가 14일 뒤 재점화하면 **새 event spawn** → current의 lifecycle `revive`로 이어질 수 있음(§8).

---

## 7. event → current 그룹화와 '고도(altitude)' 제어

`event`(discrete happening, 14일 윈도)는 micro, `current`(macro thread, 주차간 안정 ID)는 상위 고도다.

**배정 규칙(Phase 1, append-only — §8):**

```
for each event without current_id:
  c = argmax cosine_sim(event.centroid, current.centroid) over active currents
  if cosine_sim(c) >= TAU_CURRENT:           # 아래 '고도' 제어
      event.current_id = c.id  (append-only, 재배정 금지)
      current.centroid ← EMA 갱신(α=0.2)
      log nothing (정상 흡수) 또는 spawn 로그 1회(최초)
  else:
      Phase 0/1: 수동 큐레이션 큐로(미배정 event는 board 미노출)
      Phase 2:   신규 current 자동 spawn 후보
```

**'고도' 제어 = current 그래뉼래리티 노브.** macro thread 수를 **10~15개(spec §2.1, canon Go/No-Go)** 로 유지하기 위한 파라미터:

| 노브 | 의미 | 기본값 | 효과 |
|------|------|--------|------|
| `TAU_CURRENT` | event→current 흡수 cosine 컷 | **0.78** (TAU_CLUSTER보다 **낮게**) | 낮을수록 한 current가 더 많은 event를 흡수 → current 수↓·고도↑ |
| taxonomy_seed | 하향식 택소노미 seed centroid(§8) | vertical당 ~10개 | current가 미리 정의된 macro 축에 정렬 → 무한 분열 방지 |
| board cap | 노출 current 수 | 10~15 | momentum score(§3) 상위만 노출, 나머지 dormant 후보 |

**근거 1줄:** event 컷(0.84)은 "같은 사건"이라 높게, current 컷(0.78)은 "같은 macro 흐름"이라 낮게 — 두 단계 컷이 고도(altitude)를 만든다. current 수가 15 초과로 늘면 `TAU_CURRENT`를 낮추거나 택소노미 seed를 병합(중앙 거버넌스), 5 미만이면 반대로. **Phase 0/1은 매주 재군집 금지**(canon §4)이므로 고도 조정은 seed/임계 변경 + lifecycle 로그로만.

---

## 8. current ID 안정성 (canon §4·§6 LOCK)

### 8.1 Phase 1 — 하향식 택소노미 + append-only

- current ID = **text 슬러그**(`current.id`, 예 `"middle-east"`), 주차간 안정·재발급 금지(§13 churn=0).
- **하향식 택소노미**: vertical마다 사람이 정의한 macro 축(seed)을 `current.taxonomy_seed`로 미리 등록 → event는 기존 current에만 append-only 배정. **매주 재군집(re-cluster) 금지** = 구조적 불변.

```sql
-- canon §6 current
CREATE TABLE current (
  id           text PRIMARY KEY,             -- 슬러그, 안정
  vertical_id  text REFERENCES vertical(id),
  name         text,
  color_key    text REFERENCES color_registry(color_key),
  status       current_status,              -- active/merged/dormant
  merged_into  text REFERENCES current(id),
  centroid     vector(1024),
  taxonomy_seed text,                        -- 하향식 seed 식별
  coverage_config jsonb
);

-- 다대다 배정 (append-only)
CREATE TABLE article_current (
  current_id text,
  article_id uuid,
  article_published_at timestamptz,          -- 파티션 프루닝, app-FK
  is_primary boolean DEFAULT false,          -- 보조태그=false
  PRIMARY KEY (current_id, article_id)
);
```

### 8.2 split / merge / dormant — 명시 이벤트 로그

ID를 바꾸지 않고 **lifecycle을 로그로 표현**(canon §4·§6):

```sql
CREATE TYPE lifecycle_event_type AS ENUM
  ('spawn','split','merge','dormant','revive');

CREATE TABLE current_lifecycle_event (
  id                 bigserial PRIMARY KEY,
  type               lifecycle_event_type,
  current_id         text REFERENCES current(id),
  related_current_id text REFERENCES current(id),   -- split의 자식, merge의 흡수처
  occurred_at        timestamptz,
  evidence           jsonb,    -- {events:[...], jaccard:0.x, centroid_sim:0.x, sample_ids:[...]}
  actor              text      -- 'system' | editor email
);
```

의미 규칙:
- **spawn**: 새 macro 축 등장(Phase 0/1 수동 승인 후). 새 슬러그 1회 발급.
- **split**: `current_id`가 분기, `related_current_id` = 새 자식 current(새 슬러그). 원본은 유지.
- **merge**: `current_id` → `related_current_id`로 흡수. `current.status='merged'`, `merged_into=related_current_id`. **원본 ID 보존**(digest 과거 비교 위해).
- **dormant**: 활성 event 전무·volume 베이스라인 이하 지속 → `status='dormant'`. 보드 미노출, ID 유지.
- **revive**: dormant current가 새 event 흡수 시 `status='active'` 복귀(같은 ID).

**근거 1줄:** ID를 절대 바꾸지 않고 상태·관계를 로그로 표현하므로 digest의 "지난주→이번주" 비교(weekly_rank 동결)와 §13 churn=0이 구조적으로 보장된다.

### 8.3 Phase 2 — Jaccard-Hungarian 자동 발견

```
주기 배치(예: 주 1회):
  prev_clusters(member event 집합) vs. new_clusters
  cost[i][j] = 1 - Jaccard(members_i, members_j)
  match = Hungarian(cost)                       # 최적 1:1 정합
  해석:
    1↔1 고유사  → 동일 current(ID 유지)
    1→다       → split  → current_lifecycle_event(type=split)
    다→1       → merge  → (type=merge, merged_into)
    무매칭 new → spawn,  무매칭 old → dormant
```

Hungarian으로 prev/new 클러스터를 정합하고, Jaccard로 동일성을 측정 → split/merge/dormant를 **자동 감지해 lifecycle 로그에 기록**(canon: Phase 2에서 자동 발견). canon은 상위 호환 — 컬럼/임계 추가만, ID·로그 의미 변경 금지.

---

## 9. 백필 · embeddingVersion 재처리

### 9.1 백필 (동일 파이프라인 재사용)

| | Phase 0 | Phase 1 |
|--|---------|---------|
| 범위 | **8주** (geopolitics) | **6개월** (geopolitics + technology) |
| 실행 | partition별 동일 코드(cron 잡에 `--from/--to`) | Dagster partitioned asset 재실행 |
| 멱등 | url-hash upsert(§5.2)로 중복 없음 | 동일 |

**핵심:** 백필은 **실시간과 같은 파이프라인**을 시간 partition만 바꿔 돌린다(별도 코드 금지) → 백필/실시간 결과 일관성. 단 클러스터링은 **시간순 재생**(published_at 오름차순)으로 leader-follower를 재현해야 event/current 배정이 실시간과 동일해진다(centroid EMA는 순서 의존).

```
backfill(vertical, t0, t1):
  for slot in 15min_slots(t0, t1):           # 시간순
    ingest → scope → dedup → normalize → embed   # 멱등 upsert
  for article in canonical order by published_at:  # 순서 재생
    leader-follower assign (§6)
  event → current append-only (§7/§8)
```

### 9.2 embeddingVersion 재처리

모델/리비전 교체(예 `bge-m3@v1.5` → 차기) 시:

```
1. EMBED_REVISION 갱신 → embedding_version = "<model>@<new_rev>"
2. 정본(is_canonical=true) 전건 재임베딩(신 컬럼 또는 신 행 버전), 구 벡터 보존
3. HNSW 인덱스 신 벡터로 재구축(ef_construction=64, m=16)
4. τ 재캘리브레이션(§6.2) — 거리 분포가 모델마다 달라 TAU_CLUSTER 재검증 필수
5. 클러스터링 재생(§9.1) — current ID는 append-only 유지(재배정만, 재발급 금지)
6. 컷오버: 신 embedding_version로 board 서빙, 구 버전 N일 보존 후 purge
```

**근거 1줄:** `embedding_version` 컬럼이 LOCK인 이유 — 두 모델 벡터를 **혼용해 cosine 비교하면 무의미**하므로, 버전 태깅으로 동일 버전 내에서만 클러스터링·검색하고 재처리는 전건 일괄 교체한다.

---

## 10. 크롤러 SSRF 가드 (canon §12 LOCK)

본문 fetch(§1.2)는 **신뢰불가 URL**을 다루므로 모든 요청이 가드를 통과해야 한다:

```python
def guarded_fetch(url: str):
    u = urlsplit(url)
    # 1) 스킴 화이트리스트
    if u.scheme not in ("http", "https"): reject("scheme")
    # 2) 도메인 화이트리스트 — source_registry.is_whitelisted=true 만
    if not source_registry.is_whitelisted(u.hostname): reject("not_whitelisted")
    # 3) DNS 해석 → 모든 A/AAAA가 공인 IP인지 (사설망 차단)
    for ip in resolve_all(u.hostname):
        if ip.is_private or ip.is_loopback or ip.is_link_local \
           or ip.is_reserved or ip in CLOUD_METADATA_IPS:    # 169.254.169.254 등
            reject("private_ip")
    # 4) 리다이렉트: 자동추적 끔, 매 홉마다 1~3 재검증, 최대 3홉
    # 5) 핀: 검증한 IP로 직접 연결(connect-to), Host 헤더 보존 → DNS rebinding 차단
    # 6) 타임아웃·응답크기 상한(예 5MB), content-type=text/html|xml 만
```

가드 위반은 **즉시 DLQ**(`error_class='ssrf_blocked'`, 재시도 안 함, §5.4). 차단 항목:
- **화이트리스트 외 도메인** 일체(canon: 화이트리스트 도메인만).
- 사설/루프백/링크로컬/예약 IP, **클라우드 메타데이터 엔드포인트**(169.254.169.254).
- DNS rebinding(검증 IP ≠ 연결 IP), 리다이렉트를 통한 내부망 우회.

---

## 11. SourceRegistry 운용 (canon §6 LOCK)

```sql
CREATE TABLE source_registry (
  domain        text PRIMARY KEY,            -- 정규화 host
  outlet_name   text,
  tier          source_tier,                 -- 정본 선택·우선순위(§3.3)
  country       text,                        -- ISO-3166, spread_countries
  region_block  text,                        -- coverage_axis(region_block)
  outlet_type   text,                        -- coverage_axis(outlet_type)
  leaning       text,                        -- 내부전용·절대 미노출(§10 정치성향 회피)
  license_tier  license_tier,                 -- 본문 처리·인용 권리(§1.3)
  body_ttl      interval,                    -- 본문 캐시/보존 TTL → purge_after
  is_whitelisted boolean                     -- 스코핑(§2.1) + SSRF(§10)의 단일 진실원
);
```

운용 규칙:
- **단일 진실원**: 화이트리스트(스코핑·SSRF), tier(정본·우선순위), license_tier(본문/인용), region_block·outlet_type(coverage 축, §10) 모두 여기서 결정적 룩업.
- **`leaning`은 내부전용·UI/LLM 미노출**(canon §6·§10: 정치성향 라벨 회피, coverage는 region_block/outlet_type만).
- 온보딩 게이트: §1.3 라이선스 체크리스트 통과 → `is_whitelisted=true` + `license_tier`/`body_ttl` 기입. 미통과 도메인은 수집은 되되(메타) 크롤 안 함.
- 변경은 append-only 감사(`editorial_audit` 패턴) — 화이트리스트 추가/제거, tier 변경 추적.
- coverage min-n: 막대 노출은 `COVERAGE_MIN_N=5` 미달 시 숨김(§10) — registry의 region_block/outlet_type 분포가 산출 입력.

---

## 부록 A — 핵심 상수 표 (canon 그대로, 재발명 금지)

| 상수 | 값 | 출처 |
|------|-----|------|
| `EMBED_MODEL` / `EMBED_REVISION` | `bge-m3` / `v1.5` | canon §1 |
| embedding dim / 거리 | 1024 / cosine(`vector_cosine_ops`) | §1 |
| `embedding_version` 형식 | `"bge-m3@v1.5"` | §1 |
| HNSW | `m=16, ef_construction=64`, `ef_search=100` | §1 |
| `SIMHASH_HAMMING_MAX` | 3 (64-bit SimHash) | §5 |
| `TAU_CLUSTER` | 0.84 (범위 0.82~0.86) | §4 |
| `CLUSTER_TOPK` | 20 | §4 |
| `CENTROID_ALPHA` | 0.2 | §4 |
| `CLUSTER_WINDOW_DAYS` | 14 (`expires_at = last_seen + 14d`) | §4 |
| lifecycle types | `spawn,split,merge,dormant,revive` | §4·§6 |
| `COVERAGE_MIN_N` | 5 | §10 |
| coverage 축 | `region_block, outlet_type` | §10 |
| `TAU_CURRENT` (본 문서 정의) | 0.78 | §7 고도 제어 |

## 부록 B — Go/No-Go 연결 (canon §13)

- 클러스터 **purity ≥ 0.80** → §6.2 τ 캘리브레이션 라벨셋으로 측정.
- current ID **churn = 0** → §8 append-only 구조로 보장.
- coverage 결정적 룩업 **≥ 95%** → §11 source_registry + §4.3 GKG 룩업.
- board p95 staleness **≤ 5분** → §5.3 `embed`/`current_assign` watermark로 측정.
