"""Momentum v0 (Phase 0): volume(7d EMA) + persistence only. spread/accel fed as
neutral 0 into the unchanged score formula; conservative classifier (rising/
cooling by d1 sign; peaking deferred to Phase 1). CANON R6."""
from __future__ import annotations

import numpy as np

from ..config import BASELINE_WINDOW_DAYS, PERSIST_GAP_TOL, STATE_K, VOLUME_EMA_DAYS


def ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1)
    out: list[float] = []
    m: float | None = None
    for v in values:
        m = v if m is None else alpha * v + (1 - alpha) * m
        out.append(m)
    return out


def momentum_v0(daily_counts: list[int]) -> dict:
    """Compute the latest momentum_point fields from a daily article-count series.

    Cross-current/vertical score normalization (z-scores, weighted sum) is a
    Phase 1 concern; here `score` carries raw EMA volume as a placeholder.
    """
    if not daily_counts:
        return {"volume": 0.0, "persistence_days": 0, "state": "steady"}

    vol = ema([float(x) for x in daily_counts], VOLUME_EMA_DAYS)
    window = np.array(vol[-BASELINE_WINDOW_DAYS:])
    median = float(np.median(window))
    mad = float(np.median(np.abs(window - median))) or 1e-6

    # persistence: consecutive recent days above baseline median (gap-tolerant)
    persist = 0
    gap = 0
    for v in reversed(vol):
        if v > median:
            persist += 1
            gap = 0
        else:
            gap += 1
            if gap > PERSIST_GAP_TOL:
                break

    d1 = (vol[-1] - vol[-8]) / 7.0 if len(vol) >= 8 else 0.0
    tau = STATE_K * mad
    if d1 > tau:
        state = "rising"
    elif d1 < -tau:
        state = "cooling"
    else:
        state = "steady"  # peaking deferred (CANON R6)

    return {
        "volume": round(vol[-1], 3),
        "persistence_days": persist,
        "spread": 0.0,
        "spread_outlets": 0,
        "spread_countries": 0,
        "accel_d1": round(d1, 4),
        "accel_d2": 0.0,
        "baseline_median": round(median, 3),
        "baseline_mad": round(mad, 4),
        "score": round(vol[-1], 3),
        "state": state,
        "tau_state": round(tau, 4),
    }
