"""Phase 0 current assignment — semi-manual keyword rules (spec §8: "semi-manual
rules + embedding similarity"). Each headline current maps to a GDELT query used
both to assign articles and to pull its volume timeline. Embedding-based online
clustering (§5.1) replaces these rules in Phase 1.
"""

CURRENT_QUERIES: dict[str, str] = {
    "ai-governance": (
        '("AI regulation" OR "AI governance" OR "AI safety" OR "artificial intelligence act" '
        'OR "AI policy") sourcelang:english'
    ),
    "cost-of-living": (
        '("cost of living" OR inflation OR "consumer prices" OR "interest rates" '
        'OR "household budgets") sourcelang:english'
    ),
    "energy": (
        '("energy transition" OR "power grid" OR renewables OR "oil prices" OR electricity '
        'OR "natural gas") sourcelang:english'
    ),
    "climate": (
        '("climate change" OR "global warming" OR emissions OR "extreme weather" '
        'OR "climate policy") sourcelang:english'
    ),
    "middle-east": '("Middle East" OR Gaza OR Iran OR Israel OR Lebanon) sourcelang:english',
    "china": '(China OR Beijing OR Taiwan OR "Chinese government") sourcelang:english',
}
