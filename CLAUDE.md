# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: Phase 0 scaffold

The **Phase 0 scaffold is in place**: a monorepo with `pipeline/` (Python engine, skeleton), `api/` (FastAPI serving layer, seed-backed), `web/` (Next.js client — the three screens, seed-backed), `shared/` (TS types + design tokens), and `pipeline/db/schema.sql` (full DDL). The three screens render from **seed data** (spec Appendix), so they work without a DB or pipeline. The pipeline modules are mostly skeletons — real ingest/cluster/momentum/synthesis is the Phase 0/1 backlog.

**Read `docs/meridian-spec.md` first for product intent.** Then read **`docs/design/`** for the *resolved engineering decisions*. `pipeline/db/schema.sql` and `shared/src/` are generated from those docs — change the design + regenerate, don't hand-drift.

### Commands

```bash
# Web client (the board / current / digest) — http://localhost:3000 → /board
npm install
npm run dev
npm run build          # production build (also a typecheck)
npm run typecheck      # tsc --noEmit across shared + web

# Serving API (stub returns seed) — http://localhost:8000/v1/board
pip install -e .
uvicorn api.main:app --reload

# Database (Postgres + pgvector). schema + seed auto-apply on first `up`.
docker compose up -d
export DATABASE_URL=postgresql://meridian:meridian@localhost:5432/meridian
# API reads DB when DATABASE_URL is reachable (else seed); check: curl -i /v1/board | grep X-Data-Source

# Live data: seed sources, then build board/detail/digest from GDELT
python -m scripts.seed_sources          # populate source_registry (67 curated outlets)
python -m scripts.build_board           # GDELT → momentum_point / board_view / current_view / digest

# Periodic refresh (Windows Scheduled Task — run yourself; installs standing execution):
#   schtasks /create /tn MeridianRefresh /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\git\jetstream\scriptsefresh.ps1" /sc DAILY /st 06:00 /f
#   schtasks /delete /tn MeridianRefresh /f     # remove

# Python lint / tests (after `pip install -e ".[dev]"`)
ruff check pipeline api scripts
pytest
```

Locked engine constants live in `pipeline/config.py` (mirror CANON §13). Confirmed colors live in `shared/src/tokens.ts` + `pipeline/db/schema.sql` `color_registry` (CANON §14 R11).

### `docs/design/` is now the authoritative engineering source

The spec is the product brief; `docs/design/` resolves it into locked decisions (data model, momentum math, API, clustering, synthesis, client, Phase-0 plan). **On any conflict, the design docs win over the spec** — they deliberately fix several spec-internal contradictions. Authority order: **`docs/design/CANON.md` (esp. §14 RESOLUTIONS) → `docs/design/0001-foundational-decisions.md` → the detail docs.** Start at [`docs/design/README.md`](docs/design/README.md).

Spec contradictions already resolved in the design (don't "fix" them back):
- **4 momentum states, not 3:** `steady` is a first-class state (spec §3/§6 say 3, but Appendix uses `steady`). Badge = muted `#9BA3AF` + `ti-minus`.
- **Phase 0 is not literally "GDELT only":** GDELT gives URLs/signal, not article bodies — bodies come from whitelist crawling (+ news API). See `ingestion-and-clustering.md`.
- **`steady` + color governance:** per-current hues must not collide with state-badge hues (amber/coral/steel/muted reserved). Re-hue rule is locked; exact hexes await design sign-off.
- **`arc` ↔ `timeline` mapping** and many `§6` data-model gaps (vertical entity, `weekly_rank`, `embedding_version`, many-to-many membership, license/retention, `lang`) are added in `data-model.md`.

## What Meridian is (one paragraph)

A consumer app that watches the whole world's news and surfaces the **10–15 macro "currents"** beneath it, each tagged with **momentum** (rising / peaking / cooling). It is a "zoom-out button," not another feed. Three views form the core loop: **the board** (home — state of the world), **the current** (detail — one thread in ~20s), and **the digest** (weekly — what changed). Positioning is *calmer AND smarter*; the emotional target is **competence**, not wellness.

## Architecture big picture

The system splits cleanly into a **pipeline** (the automated engine) and **clients that only read published objects**. The client never touches pipeline internals — it reads denormalized `CurrentView` / `Digest` objects (spec §6).

Seven-stage data flow (spec §4):

```
Collect (GDELT + news APIs + RSS)
  → Ingest & normalize (dedupe · translate · embed)
    → Cluster (articles → events → currents)      [hard problem §5.1]
      → Momentum engine (rising/peaking/cooling)  [hard problem §5.2]
        → LLM synthesis (name · brief · digest)   [hard problem §5.3]
          → Human review gate (headline currents only)
            → Serve → board / current / digest
```

Proposed stack (spec §7, "reasonable default — not mandates"): **Python** pipeline, **Postgres + pgvector** (+ TimescaleDB for momentum time-series), thin REST/GraphQL serving layer, **Next.js** web client with hand-built SVG/D3 charts. LLM synthesis uses the **Claude API** — use a current model id (spec suggests `claude-sonnet-4-6` for cost/latency; verify current ids in the Claude docs / `claude-api` skill before pinning).

Suggested repo layout to scaffold into (spec §7): `pipeline/` (ingest, normalize, cluster, momentum, synthesis, review, db), `api/`, `web/` (`app/board`, `app/current/[id]`, `app/digest/[issue]`, `components/charts`), `shared/` (types mirroring §6, design tokens from §3).

## Cross-cutting constraints (easy to get wrong — these span many files)

These are product-defining invariants, not style preferences. Violating them breaks the concept:

- **Currents have STABLE IDs across weeks.** Record split/merge/dormant as explicit events. The digest's "last week → this week" reshuffle depends entirely on this stability. Use online (not batch) clustering. (§5.1, §6 `Current`)
- **Momentum is four signals, never naive volume.** Volume + persistence + spread (countries/outlets) + acceleration → classify trajectory shape. The whole point is distinguishing a one-time spike from steady accumulation. (§5.2)
- **LLM does grounded, structured generation only — never free generation.** Names, briefs, and timelines are drawn only from the clustered source articles, **with a source cited per item**. "How it's being covered" is **computed from the real coverage distribution**, not the model's opinion. A human gate verifies headline currents (name, neutrality, facts) before publish. If summaries lean, trust collapses. (§5.3)
- **Anti-bubble by default.** The home board is always the whole world; personalization must never hide it. Cap at **10–15 currents**. (§2.1)
- **Color = layer.** Brand teal (`#34D0BA`) is app chrome + the digest; each current owns its own hue and themes its own detail screen. This is how the user knows what layer they're on. Don't mix them. **A current's hue must never equal a momentum-state badge hue** (those 4 are reserved) — see CANON §14 R11. (§3)
- **Momentum encoding is fixed (4 states):** `rising` → amber `#F5A524` `ti-trending-up`; `peaking` → coral `#FB7A50` `ti-activity`; `cooling` → steel `#7C9CC0` `ti-trending-down`; `steady` → muted `#9BA3AF` `ti-minus`. Always pair color with icon + label (never color alone). (§3 + CANON §2)
- **Type:** sharp sans-serif everywhere; serif appears in exactly one place — the digest lede. (§3)

Design tokens (§3) and the TypeScript data model (§6) should be copied verbatim into `shared/` when scaffolding — don't re-derive them.

## Where to start

Begin at **Phase 0 — Thin slice** (spec §8), but follow the concrete, sequenced backlog + go/no-go gates in [`docs/design/phase-0-plan.md`](docs/design/phase-0-plan.md) (and the schema in `data-model.md`) rather than the spec's checklist — the design plan resolves the ordering and the body-acquisition/embedding/copyright blockers first. Recommended order: body source + embedding model + copyright → data model → momentum v0 (volume + persistence only; spread/accel as neutral `z=0`) → serving (`BoardView`) + SVG charts → Phase-1 go/no-go. All mockup data in the spec is illustrative (June 2026) and usable as seed data (see Appendix).
