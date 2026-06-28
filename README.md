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

# Serving API (stub returns seed data)
pip install -e .
uvicorn api.main:app --reload    # http://localhost:8000/v1/board

# Database schema (needs Postgres 15+ with pgvector & pgcrypto)
createdb meridian
psql "$DATABASE_URL" -f pipeline/db/schema.sql
python -m scripts.seed_phase0       # seeds vertical + ~6 currents
```

See [`docs/design/phase-0-plan.md`](docs/design/phase-0-plan.md) for the sequenced backlog and go/no-go gates.

## Status

Greenfield scaffold: structure + schema + types + tokens + seed-backed screens are in place. The pipeline modules are package skeletons (Phase 0/1 work). No external services are called yet.
