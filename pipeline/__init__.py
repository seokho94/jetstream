"""Jetstream pipeline — the automated engine (spec §4).

Stages: ingest → normalize → cluster → momentum → synthesis → review → (serve).
Phase 0 modules are skeletons; see docs/design/ for the locked design and
docs/design/phase-0-plan.md for the sequenced backlog.
"""
