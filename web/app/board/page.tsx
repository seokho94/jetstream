import { getBoard } from "@/lib/api";
import { hueFor } from "@jetstream/shared";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";
import { MomentumLegend } from "@/components/MomentumLegend";
import { Onboarding } from "@/components/Onboarding";
import { Sparkline } from "@/components/charts/Sparkline";
import { Streamgraph } from "@/components/charts/Streamgraph";

export default async function BoardPage() {
  const board = await getBoard();
  const nameById = Object.fromEntries(board.ranked.map((r) => [r.currentId, r.name]));
  return (
    <>
      <header className="appbar">
        <div className="brand">
          <span className="dot" />
          <span>
            Jetstream <span className="tagline">· 세계의 흐름, 한눈에</span>
          </span>
        </div>
        <span className="asof">
          as of {board.asOf.slice(0, 10)}
          {board.isCurrent ? "" : " · stale"}
        </span>
      </header>

      <Onboarding />

      <div className="todays">
        <p className="kicker">Today&apos;s read</p>
        <p>{board.todaysRead.paragraph}</p>
      </div>

      <div className="card">
        <Streamgraph data={board.streamgraph} />
        <div className="sg-legend">
          {board.streamgraph.map((s) => (
            <span className="sg-item" key={s.currentId}>
              <span className="sg-dot" style={{ background: hueFor(s.colorKey) }} />
              {nameById[s.currentId] ?? s.currentId}
            </span>
          ))}
        </div>
      </div>

      <p className="kicker" style={{ padding: "4px 18px 0" }}>
        흐름 · 모멘텀순 (누르면 상세)
      </p>
      <MomentumLegend />
      <ol className="ranked">
        {board.ranked.map((r) => (
          <li key={r.currentId} style={vars({ "--c": hueFor(r.colorKey) })}>
            <a className="rrow" href={`/current/${r.currentId}`}>
              <span className="rank">{r.rank}</span>
              <span className="tick" />
              <span className="nm">{r.name}</span>
              <Sparkline data={r.sparkline} color={hueFor(r.colorKey)} />
              <MomentumBadge state={r.state} />
              <span className="attn">
                <i style={{ width: `${Math.round(r.attention * 100)}%` }} />
              </span>
              <span className="chev">›</span>
            </a>
          </li>
        ))}
      </ol>

      <a className="teaser" href={`/digest/${board.digestTeaser.issue}`}>
        <span className="lede">
          Digest #{board.digestTeaser.issue} · {board.digestTeaser.lede}
        </span>
        <span className="go">열기 →</span>
      </a>
    </>
  );
}
