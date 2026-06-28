"""Momentum engine v1 (Phase 1) — CANON §3.

Two separable outputs (CANON: "랭킹점수 ≠ 상태신호"):
  • signals_for(series, …)  → per-current raw signals + a within-current STATE
    (direction from the flow's own 2-week relative trend — "which way is it
    moving", which is what the badge communicates).
  • rank(items)             → CROSS-current normalized score + rank
    (log1p volume + z across flows so absolute size doesn't dominate; weighted
    0.30·accel + 0.30·persist + 0.25·volume + 0.15·spread).
"""
from __future__ import annotations

import numpy as np

from ..config import (
    BASELINE_WINDOW_DAYS,
    PERSIST_GAP_TOL,
    STATE_REL_THRESHOLD,
    VOLUME_EMA_DAYS,
    W_ACCEL,
    W_PERSIST,
    W_SPREAD,
    W_VOLUME,
)
from .v0 import ema


def signals_for(series: list[tuple[str, int]], spread_outlets: int = 0, spread_countries: int = 0) -> dict:
    """Per-current raw signals + within-current state from a daily (date,count) series."""
    counts = [float(c) for _, c in series]
    if not counts:
        return {"state": "steady"}
    vol = ema(counts, VOLUME_EMA_DAYS)
    window = np.array(vol[-BASELINE_WINDOW_DAYS:])
    median = float(np.median(window))
    mad = float(np.median(np.abs(window - median))) or 1e-6
    volume = vol[-1]
    n = len(vol)

    # persistence: consecutive days above the flow's own baseline (gap-tolerant)
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

    # acceleration: d1 = 7-day slope of EMA; d2 = change in d1 over the prior 7 days
    d1 = (vol[-1] - vol[-8]) / 7 if n >= 8 else 0.0
    d1_prev = (vol[-8] - vol[-15]) / 7 if n >= 15 else 0.0
    d2 = (d1 - d1_prev) / 7

    # spread: geometric blend of outlet + country breadth (design §1.3)
    spread = (max(spread_outlets, 0) ** 0.5) * (max(spread_countries, 0) ** 0.5)

    # within-current state: 2-week relative trend (last 2 weeks vs the prior 2 weeks).
    recent = float(np.mean(vol[-14:])) if n >= 14 else float(np.mean(vol))
    prior = float(np.mean(vol[-28:-14])) if n >= 28 else float(np.mean(vol[: max(1, n - 14)]))
    rel = (recent - prior) / (abs(prior) + 1e-6)
    level_z = (volume - median) / (1.4826 * mad)
    t = STATE_REL_THRESHOLD
    if rel > t:
        state = "rising"
    elif rel < -t:
        state = "cooling"
    elif level_z > 0.3 and d2 < 0:
        state = "peaking"  # elevated but flattening/turning over
    else:
        state = "steady"

    return {
        "volume": round(volume, 3),
        "persistence_days": persist,
        "spread": round(spread, 3),
        "spread_outlets": int(spread_outlets),
        "spread_countries": int(spread_countries),
        "accel_d1": round(d1, 4),
        "accel_d2": round(d2, 5),
        "baseline_median": round(median, 3),
        "baseline_mad": round(mad, 4),
        "state": state,
        "tau_state": round(t, 4),
        "rel_trend": round(rel, 4),
        # accel is stored as a relative slope (d1 / baseline) so cross-current z is size-free
        "_raw": {"volume": volume, "persist": float(persist), "spread": spread, "accel": d1 / (median + 1e-6)},
    }


def rank(items: list[dict]) -> list[dict]:
    """Add cross-current normalized `score` + `rank` to each item (mutates + returns)."""
    if not items:
        return items

    def zscore(vals: list[float]) -> np.ndarray:
        a = np.array(vals, dtype=float)
        sd = a.std() or 1e-6
        return (a - a.mean()) / sd

    z_vol = zscore([np.log1p(it["_raw"]["volume"]) for it in items])  # log compresses size
    z_per = zscore([it["_raw"]["persist"] for it in items])
    z_spr = zscore([it["_raw"]["spread"] for it in items])
    z_acc = zscore([it["_raw"]["accel"] for it in items])

    for i, it in enumerate(items):
        it["z_volume"] = round(float(z_vol[i]), 3)
        it["z_persist"] = round(float(z_per[i]), 3)
        it["z_spread"] = round(float(z_spr[i]), 3)
        it["z_accel"] = round(float(z_acc[i]), 3)
        it["score"] = round(
            float(W_ACCEL * z_acc[i] + W_PERSIST * z_per[i] + W_VOLUME * z_vol[i] + W_SPREAD * z_spr[i]),
            4,
        )

    items.sort(key=lambda it: it["score"], reverse=True)
    for i, it in enumerate(items):
        it["rank"] = i + 1
    return items
