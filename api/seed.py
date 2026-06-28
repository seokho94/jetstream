"""Phase 0 seed (spec Appendix, June 2026) — same illustrative data as
shared/src/seed.ts, kept in Python so the API stub is self-contained."""
from __future__ import annotations

import datetime
import math

from .schemas import (
    ArcPoint,
    Blurb,
    BoardView,
    Brief,
    Citation,
    CoverageBucket,
    CoverageView,
    CurrentView,
    Digest,
    DigestTeaser,
    Mover,
    Movers,
    RankedRow,
    ReshuffleRow,
    Stats,
    StreamSeriesPoint,
    StreamgraphSeries,
    TimelineNode,
    TodaysRead,
)

META = [
    dict(id="ai-governance", name="AI governance", state="rising", thisRank=1, lastRank=3, attention=0.94, blurb="표준·감독 프레임워크가 빠르게 수렴하고 있습니다."),
    dict(id="cost-of-living", name="Cost of living", state="peaking", thisRank=2, lastRank=1, attention=0.86, blurb="물가 압력이 고점에서 평탄화되는 신호입니다."),
    dict(id="energy", name="Energy", state="rising", thisRank=3, lastRank=4, attention=0.75, blurb="전력망·재생에너지 투자가 꾸준히 누적되고 있습니다."),
    dict(id="climate", name="Climate", state="rising", thisRank=4, lastRank=6, attention=0.61, blurb="극단 기후 사건이 정책 논의를 끌어올렸습니다."),
    dict(id="middle-east", name="Middle East", state="cooling", thisRank=5, lastRank=2, attention=0.52, blurb="긴장이 고점을 지나 완화되는 국면입니다."),
    dict(id="china", name="China", state="steady", thisRank=6, lastRank=5, attention=0.42, blurb="극적 사건 없이 꾸준한 기저 관심이 유지됩니다."),
]

ASOF = "2026-06-28T09:00:00Z"


def _r2(x: float) -> float:
    return round(x, 2)


def _week(i: int) -> str:
    return (datetime.date(2026, 1, 11) + datetime.timedelta(days=i * 7)).isoformat()


def _spark(seed: int, state: str) -> list[float]:
    out = []
    for i in range(10):
        base = (math.sin(seed * 1.4 + i * 0.6) + 1) / 2
        drift = {
            "rising": i * 0.05,
            "cooling": -i * 0.04,
            "peaking": 0.4 - abs(i - 6) * 0.04,
        }.get(state, 0.0)
        out.append(_r2(min(1.0, max(0.05, base * 0.4 + 0.3 + drift))))
    return out


def _arc(seed: int) -> list[ArcPoint]:
    pts = []
    for i in range(24):
        base = (math.sin(seed * 1.1 + i * 0.5) + 1) / 2
        pts.append(ArcPoint(t=_week(i), value=_r2(min(1.0, max(0.05, base * 0.5 + 0.18 + i * 0.013)))))
    for k, p in enumerate([4, 9, 14, 18, 23]):
        pts[p].marker = k + 1
        pts[p].eventId = f"{seed}-e{k + 1}"
    return pts


def build_board() -> BoardView:
    ranked = [
        RankedRow(
            currentId=m["id"], name=m["name"], colorKey=m["id"], rank=m["thisRank"], state=m["state"],
            score=_r2(m["attention"]), sparkline=_spark(m["thisRank"] + 1, m["state"]), attention=m["attention"],
        )
        for m in sorted(META, key=lambda m: m["thisRank"])
    ]
    stream = [
        StreamgraphSeries(
            currentId=m["id"], colorKey=m["id"],
            series=[
                StreamSeriesPoint(t=_week(16 + w), share=_r2(0.08 + ((math.sin(mi * 1.7 + w * 0.5) + 1) / 2) * 0.18 + m["attention"] * 0.12))
                for w in range(8)
            ],
        )
        for mi, m in enumerate(META[:6])
    ]
    return BoardView(
        id=1, asOf=ASOF, generatedAt=ASOF, isCurrent=True,
        todaysRead=TodaysRead(
            paragraph="세계는 AI 거버넌스로 시선이 쏠리는 한 주였습니다 — 규제 수렴이 가속하며 1위로 올라섰고, 생활비는 고점에서 평탄화, 중동은 긴장이 한 풀 꺾였습니다.",
            asOf=ASOF,
        ),
        streamgraph=stream, ranked=ranked,
        digestTeaser=DigestTeaser(issue=12, weekOf="2026-06-22", lede="이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다."),
        stats=Stats(currentsTracked=12, newThreads=3, storiesScanned=184320), etag="seed-board-1",
    )


def build_current(cid: str) -> CurrentView | None:
    m = next((x for x in META if x["id"] == cid), None)
    if not m:
        return None
    seed = m["thisRank"] + 2
    arc = _arc(seed)
    dates = [p.t for p in arc if p.marker]
    return CurrentView(
        currentId=m["id"], name=m["name"], colorKey=m["id"], rank=m["thisRank"], state=m["state"], arc=arc,
        brief=Brief(
            whatsHappening=f'{m["name"]} — {m["blurb"]}',
            whyItMatters="단발성 스파이크가 아니라 여러 주에 걸친 꾸준한 축적이라, 올해의 방향을 가늠하는 데 의미가 큽니다.",
            citations=[Citation(text=m["blurb"], outlet="Reuters", url="https://example.com/a", charStart=0, charEnd=len(m["blurb"]))],
        ),
        timeline=[
            TimelineNode(
                node=k + 1, date=d, text=f'{m["name"]} 전개 {k + 1}: 주요 사건 요약 (시드 데이터).',
                eventId=f"{seed}-e{k + 1}", isLatest=(k == len(dates) - 1),
                sources=[Citation(text="", outlet=("AP" if k % 2 else "Reuters"), url="https://example.com/s", charStart=0, charEnd=12)],
            )
            for k, d in enumerate(dates)
        ],
        coverage=CoverageView(
            axis="region_block", minN=5,
            buckets=[
                CoverageBucket(label="Europe", pct=41, n=38),
                CoverageBucket(label="North America", pct=33, n=31),
                CoverageBucket(label="Asia", pct=26, n=22),
            ],
            hidden=[],
        ),
        asOf=ASOF, etag=f"seed-current-{cid}",
    )


def build_digest(issue: int) -> Digest:
    by_this = sorted(META, key=lambda m: m["thisRank"])
    return Digest(
        issue=issue, weekOf="2026-06-22", lede="이번 주, 세계의 관심은 사건이 아니라 축적으로 움직였다.",
        reshuffle=[ReshuffleRow(currentId=m["id"], name=m["name"], colorKey=m["id"], lastRank=m["lastRank"], thisRank=m["thisRank"]) for m in META],
        movers=Movers(
            climber=Mover(currentId="ai-governance", name="AI governance", lastRank=3, thisRank=1, note="규제 수렴 가속"),
            faller=Mover(currentId="middle-east", name="Middle East", lastRank=2, thisRank=5, note="긴장 완화"),
        ),
        blurbs=[Blurb(kicker=m["name"], body=m["blurb"]) for m in by_this[:3]],
        watchNext=[
            "AI 거버넌스: 다국적 표준 초안 발표 여부",
            "에너지: 전력망 투자 발표가 모멘텀을 굳히는지",
            "생활비: 고점 평탄화가 하강으로 전환되는지",
        ],
        stats=Stats(currentsTracked=12, newThreads=3, storiesScanned=184320),
    )


def search(q: str) -> list[dict]:
    if not q:
        return []
    ql = q.lower()
    return [dict(currentId=m["id"], name=m["name"]) for m in META if ql in m["name"].lower()]
