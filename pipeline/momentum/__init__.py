"""Momentum (spec §4 stage 4 / §5.2): volume·persistence·spread·acceleration →
normalized score + 4-state classifier.

  • momentum_v0  — Phase 0 (volume + persistence only)
  • signals_for / rank — Phase 1 engine (4 signals, cross-current normalization)
"""
from .engine import rank, signals_for
from .v0 import momentum_v0

__all__ = ["momentum_v0", "signals_for", "rank"]
