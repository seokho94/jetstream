# Jetstream — Momentum Engine (`momentum-engine.md`)

> **⚠️ 검수 반영(v2):** [CANON](CANON.md) **§14**로 갱신 — 충돌 시 §14 최우선. 적용: **R3**(board rank=live `RANK() OVER momentum_point.score`; `weekly_rank`=digest 전용) · **R4**(`arc.value`=서버 정규화 0..1) · **R6**(Phase 0=volume+persistence만, spread·accel `z=0`, peaking 연기) · **R10**(board 랭킹 게이트 `RANK_MIN_VOLUME=5`, `COVERAGE_MIN_N`과 분리). 또한 §8 예시의 `spread`는 §1.3 기하혼합 공식상 ≈16.4.

> **목적(한 줄):** 클러스터링된 `current`별 일별 시계열로부터 4개 신호(volume·persistence·spread·acceleration)를 산출·정규화하여, **랭킹 점수(`score`)** 와 **상태 신호(`state`)** 를 분리 생산하고 `momentum_point` / `weekly_rank` / `current_view.arc`를 채우는 엔진의 확정 사양.
>
> **적용 범위:**
> - **Phase 0** — vertical 1개(`geopolitics`), 수동 큐레이션 current ~10개, 8주 백필. Momentum **v0 = volume + persistence**만 정식 산출(§9). 본 문서 전체가 구속력.
> - **Phase 1** — vertical 2개(+`technology`), 온라인 클러스터링·LLM 합성·휴먼게이트. Momentum **full = 4신호 전부 + 상태 분류기 + hysteresis**.
> - **Phase 2** — 다소스·다언어 확장, split/merge 자동 발견. 본 문서의 상수/스키마는 상위 호환(추가만 허용, 의미 변경 금지).
>
> **CANON 우선.** 아래 모든 이름·상수·필드는 canon에서 그대로 가져온다. 충돌 시 canon이 이긴다.

---

## 0. 입력 계약과 출력 스키마

엔진은 일별 1행(`bucket = 1 day`)을 가정한다. 입력은 `event` / `article_current` 조인에서 파생된 흐름별 일 집계, 출력은 `momentum_point`이다.

### 0.1 출력 — `momentum_point` (PK `(current_id, t)`)

canon §6 그대로. 모든 컬럼은 엔진이 매일 채운다.

```sql
CREATE TABLE momentum_point (
  current_id      text        NOT NULL REFERENCES current(id),
  t               date        NOT NULL,              -- daily bucket
  volume          real        NOT NULL,              -- 7-day EMA of canonical article count
  persistence_days smallint   NOT NULL,              -- consecutive days above robust baseline
  spread          real        NOT NULL,              -- combined outlet+country diversity index
  spread_outlets  smallint    NOT NULL,              -- raw distinct outlets (syndication-folded)
  spread_countries smallint   NOT NULL,              -- raw distinct countries
  accel_d1        real        NOT NULL,              -- 7-day 1st derivative
  accel_d2        real        NOT NULL,              -- 14-day 2nd derivative
  baseline_median real        NOT NULL,              -- 60–90d trailing median (default 90)
  baseline_mad    real        NOT NULL,              -- 60–90d trailing MAD
  score           real        NOT NULL,              -- composite ranking score (§3)
  state           momentum_state NOT NULL,           -- {rising,peaking,cooling,steady} (§4)
  tau_state       real        NOT NULL,              -- STATE_K*MAD enter threshold used at t
  PRIMARY KEY (current_id, t)
);
CREATE INDEX ix_mp_current_t ON momentum_point (current_id, t DESC);
```

`momentum_state`는 canon §2의 LOCK ENUM:

```sql
CREATE TYPE momentum_state AS ENUM ('rising','peaking','cooling','steady');
```

> **필드명 주의:** spec §6의 `MomentumPoint`는 `persistence` / `acceleration`을 단수로 적었으나 **canon이 이긴다** → 정식 필드는 `persistence_days`, `accel_d1`, `accel_d2`. spec의 3-상태 `state` 타입도 canon §2의 **4-상태**가 정식이다.

### 0.2 엔진 상수 (canon 고정값 — 재발명 금지)

```python
# normalization / baseline
BASELINE_WINDOW_DAYS = 90      # robust baseline trailing window, range 60–90, default 90
MAD_C               = 1.4826   # MAD→σ consistency constant for z=(x-median)/(MAD_C*MAD)
EMA_VOLUME_DAYS     = 7        # volume = 7-day EMA  -> alpha = 2/(7+1) = 0.25
D1_WINDOW_DAYS      = 7        # accel_d1
D2_WINDOW_DAYS      = 14       # accel_d2
PERSIST_GAP_TOL     = 2        # persistence allows 1–2 day dips before reset

# composite score weights (sum = 1.00)
W_ACCEL   = 0.30
W_PERSIST = 0.30
W_VOLUME  = 0.25
W_SPREAD  = 0.15

# state classifier
STATE_K               = 1.0    # tau_enter = STATE_K * MAD
STATE_TAU_EXIT_RATIO  = 0.7    # tau_exit = 0.7 * tau_enter (dead-band)
STATE_HYSTERESIS_DAYS = 2      # state flips only after 2 consecutive qualifying days
```

---

## 1. 4신호의 정확한 정의와 산식

모든 신호는 **흐름 내부(self)** 시계열에서 산출한다. dedup 규칙(canon §5)에 따라 **near-dup은 volume에 1로만 기여하고 spread(outlet/country 멤버십)에는 전부 반영**된다. 즉 `event.article_count`(정본)는 volume 근거, `event.member_count`(near-dup 포함)는 spread 근거다.

### 1.1 `volume` — 일별 정본 기사수의 7일 EMA

`event.article_count`(= `is_canonical=true`인 정본만 카운트)를 흐름 단위로 합산한 일 raw count `c_t`에 7일 EMA를 적용한다.

```
alpha   = 2 / (EMA_VOLUME_DAYS + 1) = 2/8 = 0.25
ema_0   = c_0                                  # seed with first observed day
volume_t = alpha * c_t + (1 - alpha) * volume_{t-1}
```

- EMA를 쓰는 이유: 단순 7일 합/이동평균보다 최근 일에 가중을 둬 가속을 더 빨리 반영하면서도 단발 스파이크를 평활. (트레이드오프: 윈도 끝 절단 편향이 없어 백필 첫 7일은 워밍업 구간으로 간주.)
- 결손일(`c_t` 없음)은 `c_t = 0`으로 채워 EMA를 진행(흐름이 식는 신호를 보존).

### 1.2 `persistence_days` — robust baseline 초과 지속일수

흐름 자기 robust baseline `baseline_median`(§2.2) **초과 연속일수**. canon: 1~2일 결손 허용 후 리셋(`PERSIST_GAP_TOL=2`).

```python
def persistence(volume_series, baseline_median_series, gap_tol=PERSIST_GAP_TOL):
    run = 0          # current persistence_days
    gap = 0          # consecutive below-baseline days inside an active run
    for v, base in zip(volume_series, baseline_median_series):
        if v > base:
            run += 1
            gap = 0
        else:
            gap += 1
            if gap > gap_tol:      # 3rd consecutive dip -> reset
                run = 0
                gap = 0
            # else: tolerate dip, run frozen (not incremented, not reset)
    return run
```

- “초과”는 **strict `>`** (동률은 미초과). baseline은 매일 갱신되는 trailing median이므로 day별 `base`를 사용.
- 결손/dip 1~2일은 run을 **동결(freeze)**(증가도 리셋도 아님)하고, 3일째 dip에서 리셋. “4주 꾸준한 누적” 같은 흐름을 단발 휴지로 깨뜨리지 않기 위함.

### 1.3 `spread` — 신디케이션 접은 outlet·국가 다양성 + 집중도 보정

canon: 신디케이션 접은 후 outlet·country 다양성. `spread_outlets`, `spread_countries`를 **별도 보존**하고, 집중도 보정한 결합 지수를 `spread`에 저장.

raw 카운트는 `event.outlets` / `event.countries`(near-dup 멤버십 포함, syndication 접힘 반영)에서 흐름 단위 distinct 집계:

```
spread_outlets   = | distinct outlets   over active events of the flow at t |
spread_countries = | distinct countries over active events of the flow at t |
```

**집중도 보정**: 한 outlet/국가가 점유를 독식하면 “넓게 퍼짐”이 아니다. outlet 점유 분포 `p_i`(outlet i의 정본 점유율)에 대해 **정규화 엔트로피(Pielou evenness)** 로 보정한다.

```
H_out      = -Σ p_i * ln(p_i)                         # Shannon entropy of outlet shares
E_out      = H_out / ln(spread_outlets)               # evenness in [0,1]; =1 if spread_outlets<=1
E_country  = H_country / ln(spread_countries)         # same for countries

spread = (spread_outlets   * E_out)     ** 0.5  *      # geometric blend of breadth × evenness
         (spread_countries * E_country) ** 0.5
```

- geometric blend을 쓰는 이유: outlet 다양성과 국가 다양성 둘 다 있어야 “진짜 spread”. 한쪽이 0에 가까우면 곱이 눌려 과대평가를 방지. (트레이드오프: 한 축이 결손이면 `+1` 라플라스 가산으로 `ln(0)`/`0` 분모 방어.)
- `spread_outlets`, `spread_countries`를 raw로 별도 보존(canon)하여 디버깅·coverage(§10) 산출과 분리.

### 1.4 `acceleration` — `accel_d1`(7일 1차), `accel_d2`(14일 2차)

EMA 평활된 `volume`에 대한 도함수. 노이즈 억제를 위해 **OLS 기울기(최소제곱 1차 적합)** 로 추정한다(점-대-점 차분보다 안정).

```python
import numpy as np

def ols_slope(y):                      # y: equally-spaced series, returns per-day slope
    x = np.arange(len(y), dtype=float)
    x -= x.mean()
    return float((x @ (y - y.mean())) / (x @ x))

# accel_d1: slope of volume over trailing 7 days
accel_d1 = ols_slope(volume[t-6 : t+1])           # D1_WINDOW_DAYS = 7

# accel_d2: change of d1 over trailing 14 days
#   compute the d1 series, then slope of d1 over 14 days (2nd derivative proxy)
d1_series = [ols_slope(volume[i-6 : i+1]) for i in range(t-13, t+1)]
accel_d2  = ols_slope(d1_series)                   # D2_WINDOW_DAYS = 14
```

- `accel_d1 = 7일 1차도함수`, `accel_d2 = 14일 2차도함수`(canon §3) 그대로. d2를 14일로 길게 잡는 이유: 2차 미분은 노이즈 증폭이 심해 더 긴 윈도로 평활.
- 워밍업: 백필 첫 6일은 `accel_d1=0`, 첫 13일은 `accel_d2=0`으로 둠(데이터 부족 구간 외삽 금지).

---

## 2. 정규화

정규화는 **2단계**: (A) 흐름 내(self) robust z, (B) 흐름간·버티컬간 재표준화(지정학 편향 제거).

### 2.1 성분별 흐름 내 robust z (canon §3)

각 성분 volume/persistence/spread/accel을 흐름 자기 60~90일(default 90) trailing median/MAD로 robust z:

```
z = (x - median) / (MAD_C * MAD)      # MAD_C = 1.4826
```

- **volume만 `log1p` 선변환** 후 z (꼬리 무거운 카운트 분포를 정규화):
  ```
  z_vol = ( log1p(volume_t) - median_90( log1p(volume) ) )
          / ( MAD_C * MAD_90( log1p(volume) ) )
  ```
- persistence/spread/accel은 원 스케일에서 robust z (`z_persist`, `z_spread`, `z_accel`). `accel`은 `accel_d1`을 점수용 성분으로 사용(가속의 부호·크기가 “움직임”의 본질).
- MAD=0(완전 평탄 흐름) 방어: `MAD = max(MAD, EPS)`, `EPS = 1e-6`. cold-start 처리는 §6.

> `baseline_median` / `baseline_mad`는 **volume의 raw-스케일** trailing median/MAD를 `momentum_point`에 저장한다(persistence 비교·상태 τ 산출에 raw 스케일이 필요하므로). z 계산용 log-스케일 통계는 파생 중간값으로 행에 영구 저장하지 않는다.

### 2.2 robust baseline 정의

```
baseline_median = median( volume[t-89 : t+1] )     # 90-day trailing, default
baseline_mad    = median( | volume[i] - baseline_median | )   over same window
```

윈도 가용일이 60일 미만이면 cold-start(§6). 60~90일이면 가용 구간으로 축소(canon 범위 60~90).

### 2.3 흐름간·버티컬간 재표준화 (지정학 편향 제거)

흐름 내 z만 쓰면 “원래 시끄러운 흐름”(지정학)이 구조적으로 높은 절대 volume 때문에 랭킹을 독식한다. canon: **흐름간·버티컬간 재표준화**. 같은 `as_of` 날짜의 모든 활성 흐름 z-벡터를 **버티컬 내에서 다시 robust-standardize**한 뒤, 버티컬 간 비교를 위해 한 번 더 표준화한다.

```python
# step A: per-component self z already computed: z_vol, z_persist, z_spread, z_accel
# step B1: within-vertical cross-flow re-standardization (per day, per component)
for comp in ("z_vol","z_persist","z_spread","z_accel"):
    col = [flow[comp] for flow in active_flows_in_vertical]
    med, mad = np.median(col), median_abs_dev(col)
    for flow in active_flows_in_vertical:
        flow[comp] = (flow[comp] - med) / (MAD_C * max(mad, EPS))

# step B2: cross-vertical: standardize each vertical's distribution to common scale
#   (removes "geopolitics is structurally louder than technology" bias)
for comp in (...):
    # subtract vertical-level median so a hot vertical doesn't dominate the board
    flow[comp] -= vertical_median[comp]
```

- 효과: “지정학이라서 항상 1위”가 아니라 **각 흐름이 자기·동료 대비 얼마나 비정상적으로 움직였나**로 랭킹. spec §1의 anti-bubble / 전세계 board 원칙과 정합.
- Phase 0는 vertical 1개라 step B2가 항등(no-op)이지만 코드 경로는 동일하게 유지(Phase 1에서 `technology` 추가 시 즉시 동작).

---

## 3. Composite score — 가중합·가중치 근거, 랭킹/상태 분리

### 3.1 산식 (canon LOCK)

```
score = W_ACCEL*z_accel + W_PERSIST*z_persist + W_VOLUME*z_vol + W_SPREAD*z_spread
      = 0.30*z_accel + 0.30*z_persist + 0.25*z_vol + 0.15*z_spread
```

`z_*`는 §2.3까지 재표준화를 마친 값. `board_view.ranked` / `weekly_rank.rank`는 이 `score` **내림차순**(canon §3).

### 3.2 가중치 근거 (한 줄씩)

| 성분 | 가중치 | 근거 |
|------|--------|------|
| `z_accel` | **0.30** (`W_ACCEL`) | 제품의 핵심 약속은 “**어디로 움직이는가**” — 가속이 momentum-first 랭킹의 1순위 신호. |
| `z_persist` | **0.30** (`W_PERSIST`) | 단발 스파이크와 “꾸준한 누적”을 가르는 핵심. 가속과 동률로 둬 **터지는 흐름과 지속되는 흐름을 균형** 있게 상위 노출. |
| `z_vol` | **0.25** (`W_VOLUME`) | 절대 주목도. 단, 흐름간 재표준화 후라 “원래 큰 흐름” 편향은 제거됨 → 가속/지속보다 한 단계 낮게. |
| `z_spread` | **0.15** (`W_SPREAD`) | 지리·매체 breadth는 신뢰도 보강 신호지만 후행성이 커 최저 가중. |

합 = 1.00. **랭킹은 “움직임(60%) + 규모(25%) + 확산(15%)”** 의 의도적 배분.

### 3.3 랭킹 점수 ≠ 상태 신호 (분리)

canon §3 LOCK: **`score`는 랭킹 전용, `state`는 별도 산출.** 같은 `accel`을 쓰더라도:
- `score`는 z의 **크기**(연속값)를 가중합 → 순위.
- `state`는 `accel_d1`/`accel_d2`/레벨의 **부호·형태**를 분류기에 통과(§4) → 라벨.

이유: 가속이 음수라도(=cooling) volume·persistence·spread가 높으면 랭킹 상위일 수 있다. “상위인데 식는 중”을 표현해야 제품이 정직하다. 두 값을 한 숫자로 섞으면 이 정보가 손실된다.

---

## 4. 상태 분류 (rising / peaking / cooling / steady)

`state`는 **accel 형태 분류기**(canon §2/§3). 입력: `accel_d1`, `accel_d2`, 그리고 “최근 피크 부근” 레벨 신호.

### 4.1 MAD 비례 임계 τ

```
tau_enter = STATE_K * baseline_mad          # STATE_K = 1.0   (canon: tau_state = k*MAD)
tau_exit  = STATE_TAU_EXIT_RATIO * tau_enter # = 0.7 * tau_enter  (dead-band)
tau_state (stored in momentum_point) = tau_enter at t
```

- 임계를 **MAD 비례**로 두는 이유: 흐름마다 변동성이 다르다. 절대 임계는 시끄러운 흐름을 늘 rising/cooling으로 오분류. `baseline_mad` 비례면 “자기 변동성 대비 유의미한 기울기”만 트리거.
- `d1≈0` 판정은 dead-band: `|accel_d1| ≤ tau_exit`이면 0으로 간주.
- `d2≈0`/`d2≥0`/`d2<0`도 `tau_exit` dead-band 적용(작은 2차 도함수는 0 취급).

### 4.2 원시 분기 규칙 (canon §2 정의 그대로)

“최근 피크 부근” = 현재 `volume_t ≥ 0.9 * max(volume[t-13:t+1])` (최근 14일 피크의 90% 이상). 레벨 신호.

```python
def classify_raw(d1, d2, volume_t, recent_peak, tau_enter, tau_exit):
    near_peak = volume_t >= 0.9 * recent_peak
    if d1 >  tau_enter and d2 >= -tau_exit:
        return "rising"                       # d1>0, d2>=0  (accelerating)
    if abs(d1) <= tau_exit and d2 < -tau_exit and near_peak:
        return "peaking"                      # d1~0, d2<0, near recent peak (high but flattening)
    if d1 < -tau_enter:
        return "cooling"                      # d1<0 (decelerating)
    return "steady"                           # none of the triggers (baseline-ish, neutral)
```

매핑(canon §2, 색 단독 인코딩 금지 → 항상 아이콘+라벨):

| state | 트리거 | 배지 색 | 아이콘 |
|-------|--------|---------|--------|
| `rising`  | `d1>0, d2≥0` | amber `#F5A524` | `ti-trending-up` |
| `peaking` | `d1≈0, d2<0`, 최근 피크 부근 | coral `#FB7A50` | `ti-activity` |
| `cooling` | `d1<0` | steel `#7C9CC0` | `ti-trending-down` |
| `steady`  | 위 어느 트리거도 아님 | muted `#9BA3AF` | `ti-minus` |

### 4.3 Hysteresis (플리커 방지)

canon §3: 진입 `tau_enter`, 이탈 `tau_exit=0.7*tau_enter`, **상태 전환은 2일 연속 충족 시 확정**(`STATE_HYSTERESIS_DAYS=2`).

```python
def commit_state(prev_state, raw_today, raw_yesterday):
    # flip only when the NEW raw label held for 2 consecutive days
    if raw_today != prev_state and raw_today == raw_yesterday:
        return raw_today        # confirmed flip
    return prev_state           # hold previous (dead-band + 2-day persistence)
```

- 진입/이탈 비대칭(enter > exit)으로 **dead-band**: 임계 근처 미세 진동이 매일 라벨을 바꾸지 못함.
- 2일 연속 규칙으로 단발 노이즈가 board 배지를 깜빡이게 하는 것을 차단. `state-인간판단 일치 ≥ 70%`(canon §13 Go/No-Go)의 핵심 안정화 장치.

---

## 5. 랭킹 산출 · tie-break · 순위 안정성

### 5.1 board / weekly_rank 랭킹

```sql
-- daily board ranking: per as_of, order by score desc within vertical
SELECT current_id, score, state,
       RANK() OVER (ORDER BY score DESC, ...tiebreak...) AS rank
FROM momentum_point
WHERE t = :as_of;
```

`board_view.ranked`는 매 `as_of` 재계산(live state). `weekly_rank`는 **이슈 주차당 1회 캡처 후 동결**(canon §6: “보여진 사실” 불변):

```sql
CREATE TABLE weekly_rank (
  issue      int   NOT NULL,
  current_id text  NOT NULL REFERENCES current(id),
  week_of    date  NOT NULL,
  rank       int   NOT NULL,
  score      real  NOT NULL,
  state      momentum_state NOT NULL,
  captured_at timestamptz NOT NULL,
  PRIMARY KEY (issue, current_id)
);
```

digest의 reshuffle(last-week rank → this-week rank)은 두 `weekly_rank` 행 비교로만 산출 → 한번 발행된 순위는 절대 사후 변경 안 됨.

### 5.2 Tie-break (결정적·재현 가능)

`score` 동점 시 순서가 흔들리지 않도록 **결정적 다단계 tie-break**:

```
ORDER BY
  score            DESC,      -- 1. composite
  z_accel          DESC,      -- 2. movement first (제품 약속)
  z_persist        DESC,      -- 3. sustained over spiky
  volume           DESC,      -- 4. absolute attention (raw EMA)
  current_id       ASC        -- 5. stable slug -> fully deterministic, no random
```

`current_id`(canon: 슬러그·주차간 안정)를 최종 키로 둬 **완전 결정적**. 같은 입력이면 항상 같은 순위(재현성, 감사 가능).

### 5.3 순위 안정성

- **current ID churn = 0**(canon §13): current ID는 append-only 배정(canon §4)이라 재군집으로 id가 바뀌지 않음 → 주간 reshuffle 비교가 항상 유효.
- **score 평활:** `score`는 EMA volume·robust z 기반이라 이미 평활. 추가로 rank 자체에 hysteresis는 두지 않음(랭킹은 “현재 사실”, 동결은 weekly_rank가 담당).
- **min-n 게이트:** 활성 event가 너무 적은 흐름(`event.article_count` 합 < `COVERAGE_MIN_N=5` 일 수준)은 board 랭킹에서 제외(cold-start/dormant, §6) → 희소 흐름의 노이즈가 상위를 오염시키지 않음.

---

## 6. Cold-start · 계절성/요일 보정

### 6.1 Cold-start (신규/희소/dormant)

robust baseline은 trailing 윈도가 필요한데, 신규/희소 흐름은 윈도가 비어 z가 발산한다.

| 상황 | 판정 | 처리 |
|------|------|------|
| **신규(new)** | `current` 가용일수 `< 14d` | `score=NULL`, `state='steady'` 강제. board 랭킹 **제외**(노출 보류). lifecycle `spawn` 로그(canon §4). |
| **희소(sparse)** | 가용일 14~59d | baseline 윈도를 가용 구간으로 축소(min 14d). MAD floor `EPS`. z는 산출하되 **shrinkage**: `z' = z * sqrt(n/60)`(표본 적을수록 0으로 수축) → 과신 방지. |
| **성숙(mature)** | ≥ 60d | §2 정식 경로(60~90d, default 90). |
| **dormant** | 최근 14d raw count 합 = 0 (canon §4 `CLUSTER_WINDOW_DAYS=14` 만료) | `state='cooling'`로 마지막 표기 후, lifecycle `dormant` 로그. board에서 hide. `revive` 시 sparse로 재진입. |

- shrinkage 근거: 적은 표본의 robust z는 분산이 커 가속을 과대평가 → `sqrt(n/60)` 감쇠로 “충분히 관측된 흐름”만 상위로(트레이드오프: 진짜 급부상 신규 흐름은 며칠 지연 노출되지만, 오탐보다 안전).

### 6.2 계절성·요일 보정 노트

뉴스 volume은 **주말·공휴일에 구조적으로 감소**(요일 효과)한다. 보정하지 않으면 월요일마다 “rising”, 토요일마다 “cooling” 오탐.

- **요일 보정(Phase 1 권장, Phase 0 옵션):** 흐름 무관 **vertical-레벨 요일 계수** `dow_factor[d]`를 trailing 90일로 추정(`median(volume on weekday d) / median(volume all days)`), volume을 보정 후 z/accel 산출:
  ```
  volume_adj_t = volume_t / dow_factor[ weekday(t) ]
  ```
- 보정은 **z/accel/state 입력에만** 적용. `momentum_point.volume`에는 **raw EMA(미보정)** 를 저장(arc·표시는 실제 관측치여야 함). 보정은 파생 통계 단계 한정.
- **계절성:** 장기(연 단위) 계절성은 Phase 0/1 데이터(8주~수개월)로 추정 불가 → **명시적으로 보정 안 함**(데이터 누적 후 Phase 2에서 STL 분해 검토). 지금 도입하면 과적합. 트레이드오프: 단기 요일 효과만 잡고 연 계절성은 보류.

---

## 7. MomentumPoint → arc 파생 · 다운샘플링/보존

### 7.1 파생

`current_view.arc`(jsonb, canon §6)는 `momentum_point.volume` 시계열의 **표시용 다운샘플**. 약 6개월 attention 곡선 + 숫자 이벤트 마커.

```ts
// current_view.arc element
type ArcPoint = {
  t: string;            // ISO date (bucket)
  value: number;        // displayed attention = momentum_point.volume (raw EMA, unadjusted)
  marker?: 1|2|3|4|5;   // event marker; arc[].marker === timeline[].node (canon §6)
  eventId?: string;     // shared with timeline node (canon §6)
};
```

- **arc↔timeline 바인딩(canon §6):** `arc[].marker (1..5) = timeline[].node (1..5)`, 양쪽 `eventId` 공유. 마커는 임의 다운샘플 점이 아니라 **실제 이벤트 모먼트**(해당 흐름의 상위 5개 `event`, 예: peak/spawn/최신)에 앵커.

### 7.2 다운샘플링

- **표시 해상도:** 6개월 = ~180 daily point → 모바일 SVG에 과밀. **LTTB(Largest-Triangle-Three-Buckets)** 로 ~60~90점으로 다운샘플 → 시각적 피크/형태 보존(단순 평균 다운샘플은 피크를 깎음).
- **마커는 절대 다운샘플로 잃지 않음:** LTTB 적용 후, 5개 이벤트 모먼트 t는 **강제 포함**(있으면 유지, 없으면 삽입). 마커 t의 `value`는 raw `momentum_point.volume` 그대로.
- **streamgraph share:** board의 streamgraph는 다른 파생물 — `board_view.streamgraph`의 share는 **서버에서 정규화**(canon §7/§8, 클라 비계산). arc(개별 current 절대값)와 streamgraph(흐름간 share)는 산출 경로 분리.

### 7.3 보존(retention)

| 객체 | 입도 | 보존 |
|------|------|------|
| `momentum_point` | daily, 전 컬럼 | **무손실 영구 보존**(정본 시계열·감사·재계산 근거). TimescaleDB 또는 시간버킷 테이블(spec §6). |
| `current_view.arc` | 다운샘플 ~60~90점 | 파생·재생성 가능(원본은 `momentum_point`). Draft/Published 2-store(canon §6/§11). |
| `weekly_rank` | weekly 캡처 | **동결·불변**(canon §6). |

원칙: **raw(`momentum_point`)는 절대 손실 없이 보존, 표시물(arc)은 언제든 재파생.** 재계산/임계 튜닝 시 arc만 재생성하면 됨.

---

## 8. 워크된 수치 예시 (1개)

흐름 `middle-east`, `t = 2026-06-28` 기준. 최근 10일 일별 정본 raw count `c`:

```
days   : t-9  t-8  t-7  t-6  t-5  t-4  t-3  t-2  t-1   t
c_t    :   8   10    9   12   14   15   18   22   25   30
```

**(1) volume (7-day EMA, alpha=0.25, seed=c_0=8):**

```
EMA: 8.00, 8.50, 8.63, 9.47, 10.60, 11.70, 13.28, 15.46, 17.84, 20.88
volume_t = 20.88
```

**(2) baseline (90d trailing, 가정값):** `baseline_median = 12.0`, `baseline_mad = 4.0`.

**(3) persistence_days:** volume이 12.0을 초과한 첫 날은 `t-3`(13.28) → `t-3,t-2,t-1,t` 연속 4일, dip 없음 →
```
persistence_days = 4
```

**(4) accel:**
- `accel_d1` = OLS slope of EMA over t-6..t (`9.47..20.88`) ≈ **+1.75 /day** (>0)
- `accel_d2` = 14일 d1 시계열의 기울기. 전주 d1≈+0.90 → 금주 +1.75 → **+0.06 /day²** (≥0)

**(5) 흐름 내 robust z (가정 trailing 통계):**

| 성분 | 값(원/변환) | median | MAD | z |
|------|-------------|--------|-----|---|
| volume | `log1p(20.88)=3.086` | `log1p(12)=2.565` | `0.30` | `(3.086-2.565)/(1.4826*0.30)=` **1.171** |
| persistence | `4` | `2.0` | `1.5` | `(4-2)/(1.4826*1.5)=` **0.899** |
| spread | `spread=24.0` (28 outlets·E=0.86, 14 ctry·E=0.80 → geo-blend) | `18.0` | `6.5` | `(24-18)/(1.4826*6.5)=` **0.623** |
| accel | `accel_d1=1.75` | `0.20` | `0.80` | `(1.75-0.20)/(1.4826*0.80)=` **1.307** |

(Phase 0 vertical 1개 → §2.3 cross-vertical 재표준화는 no-op. cross-flow 단계는 동료 흐름 분포에 따라 적용되나, 본 예시는 self-z를 그대로 사용한다고 가정.)

**(6) composite score:**

```
score = 0.30*1.307 + 0.30*0.899 + 0.25*1.171 + 0.15*0.623
      = 0.392 + 0.270 + 0.293 + 0.093
      = 1.048
```

**(7) state:**

```
tau_enter = STATE_K * baseline_mad_accel = 1.0 * 0.80 = 0.80
tau_exit  = 0.7 * 0.80 = 0.56
accel_d1 = 1.75 > tau_enter(0.80)  AND  accel_d2 = 0.06 >= -tau_exit(-0.56)
  -> raw label = "rising"
```

전일도 raw=`rising`이었다고 가정 → 2일 연속 충족 → **`state = 'rising'` 확정**(amber `#F5A524` + `ti-trending-up`).

**(8) 기록되는 `momentum_point` 행:**

```json
{
  "current_id": "middle-east", "t": "2026-06-28",
  "volume": 20.88, "persistence_days": 4,
  "spread": 24.0, "spread_outlets": 28, "spread_countries": 14,
  "accel_d1": 1.75, "accel_d2": 0.06,
  "baseline_median": 12.0, "baseline_mad": 4.0,
  "score": 1.048, "state": "rising", "tau_state": 0.80
}
```

---

## 9. Phase 0 v0 (volume + persistence) vs Phase 1 full

spec §8: Phase 0 “Momentum v0: volume + persistence”, Phase 1 “add spread + acceleration; tune state thresholds”. canon은 두 phase에 동일 적용 — **차이는 산출 범위와 자동화 수준이지, 상수·스키마의 변형이 아니다.**

| 항목 | Phase 0 — v0 | Phase 1 — full |
|------|--------------|----------------|
| 산출 신호 | `volume`(7d EMA), `persistence_days`만 **정식 운영** | 4신호 전부(`+spread, +accel_d1, +accel_d2`) |
| `momentum_point` 컬럼 | **전 컬럼 존재**(스키마 불변). v0 미사용 신호는 산출은 하되 `spread`/`accel`을 score에 **0 기여로 두지 않고**, 아래 score 규칙으로 처리 | 전 컬럼 정식 채움 |
| `score` | canon 가중치 식 그대로 사용하되, 미성숙 신호는 **`z=0`(중립)** 로 입력 → 사실상 `0.30*z_persist + 0.25*z_vol` 지배. 가중치 상수는 **변형 금지**(canon) | `0.30*z_accel+0.30*z_persist+0.25*z_vol+0.15*z_spread` 완전체 |
| `state` 분류 | accel이 아직 거칠어 `rising/peaking/cooling`은 보수적, 대부분 `steady`. 단순 d1 부호(7d EMA 차분)로 rising/cooling 근사, peaking은 보류 | 4-상태 분류기 + d2 + near-peak + hysteresis 정식 |
| τ / hysteresis | `tau_enter=STATE_K*MAD`, 2일 연속 규칙 **그대로 적용**(상수 불변) | 동일 + `peaking` 레벨 분기 활성 |
| current ID | 수동 큐레이션 ~10개, append-only(churn=0) | 하향식 택소노미 자동 배정(canon §4), 동일 안정성 |
| 요일/계절 보정 | 요일 보정 옵션(8주 백필이라 추정 약함), 계절성 미보정 | 요일 보정 권장, 계절성 여전히 보류 |
| 백필 | 8주 | 연속 운영 |

핵심: **Phase 0와 Phase 1은 같은 테이블·같은 상수·같은 식**을 쓴다. v0는 그 식에서 아직 신뢰 못 하는 신호(spread/accel)를 **중립(z=0)으로 입력**할 뿐, 가중치(`W_*`)나 컬럼이나 ENUM을 바꾸지 않는다(canon 상위 호환 원칙). Phase 1 전환은 코드 토글(신호 활성)이지 마이그레이션이 아니다.

---

## 10. 산출 파이프라인 의사코드 (일 1회, 흐름별)

```python
def compute_momentum_point(current_id, t):
    c = daily_canonical_counts(current_id, upto=t)          # event.article_count sum/day
    volume = ema(c, alpha=0.25)                             # §1.1
    base_med, base_mad = robust_baseline(volume, win=BASELINE_WINDOW_DAYS)  # §2.2

    persistence_days = persistence(volume, base_med, PERSIST_GAP_TOL)        # §1.2
    s_out, s_ctry, spread = spread_index(current_id, t)                      # §1.3
    d1 = ols_slope(volume[t-6:t+1])                                          # §1.4
    d2 = ols_slope([ols_slope(volume[i-6:i+1]) for i in range(t-13,t+1)])    # §1.4

    # §2.1 self robust z
    z_vol     = rz(log1p(volume[t]), log1p(volume), win=BASELINE_WINDOW_DAYS)
    z_persist = rz(persistence_days, persistence_series)
    z_spread  = rz(spread, spread_series)
    z_accel   = rz(d1, d1_series)
    z = cross_flow_then_cross_vertical(z_vol, z_persist, z_spread, z_accel)  # §2.3

    score = (W_ACCEL*z.accel + W_PERSIST*z.persist
             + W_VOLUME*z.vol + W_SPREAD*z.spread)                           # §3
    if is_cold_start(current_id, t):                                        # §6
        score, forced = apply_cold_start(score)

    tau_enter = STATE_K * base_mad                                          # §4.1
    raw   = classify_raw(d1, d2, volume[t], recent_peak(volume,14),
                         tau_enter, STATE_TAU_EXIT_RATIO*tau_enter)         # §4.2
    state = commit_state(prev_state(current_id), raw, raw_yesterday(current_id))  # §4.3

    upsert_momentum_point(current_id, t, volume, persistence_days, spread,
        s_out, s_ctry, d1, d2, base_med, base_mad, score, state, tau_enter)
```

랭킹·weekly capture·arc 재파생은 별도 잡(§5, §7)에서 `momentum_point`를 읽어 수행한다.
