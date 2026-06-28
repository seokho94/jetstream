"""Jetstream serving API — thin REST/BFF over the published store (spec §4 stage 7).

Phase 0 returns seed data so the client renders without the pipeline. Phase 1
swaps `seed` for reads of current_view/board_view/digest (store='published').
Contract: docs/design/api-contract.md.
"""
