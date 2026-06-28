"""Momentum (spec §4 stage 4 / §5.2): volume·persistence·spread·acceleration →
normalized score + 4-state classifier. Phase 0 runs v0 (volume+persistence).
"""
from .v0 import momentum_v0

__all__ = ["momentum_v0"]
