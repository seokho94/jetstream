-- Phase 0 seed: one vertical + ~6 hand-curated currents (stable IDs).
-- Auto-applied after 01-schema.sql by docker-entrypoint-initdb.d.
-- Equivalent to `python -m scripts.seed_phase0`. Idempotent.

INSERT INTO vertical (id, name) VALUES ('geopolitics', 'Geopolitics')
  ON CONFLICT DO NOTHING;

INSERT INTO current (id, vertical_id, name, color_key) VALUES
  ('ai-governance',  'geopolitics', 'AI governance',  'ai-governance'),
  ('cost-of-living', 'geopolitics', 'Cost of living', 'cost-of-living'),
  ('energy',         'geopolitics', 'Energy',         'energy'),
  ('climate',        'geopolitics', 'Climate',        'climate'),
  ('middle-east',    'geopolitics', 'Middle East',    'middle-east'),
  ('china',          'geopolitics', 'China',          'china')
  ON CONFLICT DO NOTHING;
