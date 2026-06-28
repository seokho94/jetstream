# Meridian

> **The world, zoomed out.** A calm, intelligent way to see where global news is actually heading — not more headlines, but the *currents* underneath and which way they're moving.

This repo is the **Phase 0** scaffold. The product brief is [`docs/meridian-spec.md`](docs/meridian-spec.md); the **authoritative engineering design** lives in [`docs/design/`](docs/design/README.md) (start at `CANON.md`). On conflict, the design docs win over the spec.

## Layout

```
pipeline/   Python data engine (ingest · normalize · cluster · momentum · synthesis · review · db)
api/        FastAPI serving layer — reads the published store (Phase 0: returns seed data)
web/        Next.js client — the board / current / digest (reads seed in Phase 0)
shared/     @meridian/shared — TS types (data-model §2) + design tokens (confirmed colors)
docs/       spec + design docs + color mockup
```

## Quickstart (Phase 0)

The web client renders from **seed data**, so you can see the three screens without a database or pipeline.

```bash
# Web (the board / current / digest)
npm install
npm run dev            # http://localhost:3000  → /board

# Serving API — reads DB when DATABASE_URL is set, else seed
pip install -e .
uvicorn api.main:app --reload    # http://localhost:8000/v1/board

# Database (Postgres + pgvector via Docker — schema + seed auto-applied on first boot)
docker compose up -d
export DATABASE_URL=postgresql://meridian:meridian@localhost:5432/meridian
uvicorn api.main:app --reload       # API now reads the DB → header X-Data-Source: db
# No Docker? apply to any Postgres 15+ (pgvector + pgcrypto):
#   psql "$DATABASE_URL" -f pipeline/db/schema.sql
#   psql "$DATABASE_URL" -f pipeline/db/seed_phase0.sql   # or: python -m scripts.seed_phase0
```

See [`docs/design/phase-0-plan.md`](docs/design/phase-0-plan.md) for the sequenced backlog and go/no-go gates.

## Status

Phase 0: the monorepo builds and runs end to end (web → serving API → seed, or Postgres when `DATABASE_URL` is reachable). A real GDELT collector (`pipeline/ingest/gdelt.py`) and the Postgres path (`docker compose up`, schema + seed auto-applied) are in place. Bodies, embeddings, clustering, and LLM synthesis remain the Phase 0/1 backlog.
