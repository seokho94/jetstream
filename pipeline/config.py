"""Locked engine constants — CANON §13 + momentum-engine / ingestion design.
Single source for the pipeline; keep in sync with docs/design/CANON.md."""

# Embeddings (CANON §1)
EMBED_MODEL = "bge-m3"
EMBED_REVISION = "v1.5"
EMBED_VERSION = f"{EMBED_MODEL}@{EMBED_REVISION}"
EMBED_DIM = 1024
EMBED_DISTANCE = "cosine"
HNSW = {"m": 16, "ef_construction": 64, "ef_search": 100}

# Dedup (CANON §5)
SIMHASH_HAMMING_MAX = 3

# Clustering (CANON §4)
CLUSTER_TAU = 0.84  # range 0.82–0.86
CLUSTER_TOPK = 20
CENTROID_ALPHA = 0.2
CLUSTER_WINDOW_DAYS = 14

# Momentum (CANON §3)
VOLUME_EMA_DAYS = 7
PERSIST_GAP_TOL = 2
BASELINE_WINDOW_DAYS = 90  # 60–90
W_ACCEL, W_PERSIST, W_VOLUME, W_SPREAD = 0.30, 0.30, 0.25, 0.15
STATE_K = 1.0
STATE_REL_THRESHOLD = 0.08  # 2-week relative-trend band for rising/cooling
STATE_HYSTERESIS_DAYS = 2
STATE_DEADBAND = 0.7
STATES = ("rising", "peaking", "cooling", "steady")

# Ranking / coverage gates (CANON §10, R10)
RANK_MIN_VOLUME = 5
COVERAGE_MIN_N = 5

# LLM synthesis (CANON §9). Verify current model ids in the Claude docs before pinning.
LLM_BODY_TOK = 2500
LLM_CURRENT_TOK_CAP = 60000
SYNTHESIS_MODEL = "claude-sonnet-4-6"
SYNTHESIS_MODEL_HARD = "claude-opus-4-8"

# Serving (CANON §7)
ISR_REVALIDATE = 180
POLL_INTERVAL = 60
