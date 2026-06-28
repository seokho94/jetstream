"""Published-object schemas (pydantic) — mirror docs/design/data-model.md §2.
The client reads only these; pipeline internals never leak here."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

MomentumState = Literal["rising", "peaking", "cooling", "steady"]


class ArcPoint(BaseModel):
    t: str
    value: float  # server-normalized 0..1 (CANON R4)
    marker: Optional[int] = None  # 1..5
    eventId: Optional[str] = None


class Citation(BaseModel):
    text: str
    outlet: str
    url: str
    charStart: int
    charEnd: int


class TimelineNode(BaseModel):
    node: int
    date: str
    text: str
    eventId: Optional[str] = None
    sources: list[Citation] = []
    isLatest: bool = False


class CoverageBucket(BaseModel):
    label: str
    pct: float
    n: int


class CoverageView(BaseModel):
    axis: str
    minN: int
    buckets: list[CoverageBucket]
    hidden: list[str] = []


class Brief(BaseModel):
    whatsHappening: str
    whyItMatters: str
    citations: list[Citation] = []


class CurrentView(BaseModel):
    currentId: str
    store: str = "published"
    version: int = 1
    name: str
    colorKey: str
    rank: int
    state: MomentumState
    arc: list[ArcPoint]
    brief: Brief
    timeline: list[TimelineNode]
    coverage: CoverageView
    asOf: str
    isLastKnownGood: bool = True
    etag: str
    lang: str = "en"


class StreamSeriesPoint(BaseModel):
    t: str
    share: float


class StreamgraphSeries(BaseModel):
    currentId: str
    colorKey: str
    series: list[StreamSeriesPoint]


class RankedRow(BaseModel):
    currentId: str
    name: str
    colorKey: str
    rank: int
    state: MomentumState
    score: float
    sparkline: list[float]
    attention: float


class TodaysRead(BaseModel):
    paragraph: str
    asOf: str


class DigestTeaser(BaseModel):
    issue: int
    weekOf: str
    lede: str


class Stats(BaseModel):
    currentsTracked: int
    newThreads: int
    storiesScanned: int


class BoardView(BaseModel):
    id: int
    asOf: str
    generatedAt: str
    isCurrent: bool = True
    todaysRead: TodaysRead
    streamgraph: list[StreamgraphSeries]
    ranked: list[RankedRow]
    digestTeaser: DigestTeaser
    stats: Stats
    etag: str
    lang: str = "en"


class Mover(BaseModel):
    currentId: str
    name: str
    lastRank: int
    thisRank: int
    note: str


class Movers(BaseModel):
    climber: Mover
    faller: Mover


class ReshuffleRow(BaseModel):
    currentId: str
    name: str
    colorKey: str
    lastRank: int
    thisRank: int


class Blurb(BaseModel):
    kicker: str
    body: str


class Digest(BaseModel):
    issue: int
    weekOf: str
    store: str = "published"
    lede: str
    reshuffle: list[ReshuffleRow]
    movers: Movers
    blurbs: list[Blurb]
    watchNext: list[str]
    stats: Stats
    lang: str = "en"
