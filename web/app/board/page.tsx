import { getBoard } from "@/lib/api";
import { hueFor } from "@jetstream/shared";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";
import { Sparkline } from "@/components/charts/Sparkline";
import { Streamgraph } from "@/components/charts/Streamgraph";

export default async function BoardPage() {
  const board = await getBoard();
  return (
    <>
      <header className="appbar">
        <div className="brand">
          <span className="dot" />
          Jetstream
        </div>
        <span className="asof">
          as of {board.asOf.slice(0, 10)}
          {board.isCurrent ? "" : " · stale"}
        </span>
      </header>

      <div className="todays">
        <p className="kicker">Today&apos;s read</p>
        <p>{board.todaysRead.paragraph}</p>
      </div>

      <div className="card">
        <Streamgraph data={board.streamgraph} />
      </div>

      <p className="kicker" style={{ padding: "4px 18px 0" }}>
        Currents · 모멘텀순
      </p>
      <ol className="ranked">
        {board.ranked.map((r) => (
          <li className="rrow" key={r.currentId} style={vars({ "--c": hueFor(r.colorKey) })}>
            <span className="rank">{r.rank}</span>
            <span className="tick" />
            <a className="nm" href={`/current/${r.currentId}`}>
              {r.name}
            </a>
            <Sparkline data={r.sparkline} color={hueFor(r.colorKey)} />
            <MomentumBadge state={r.state} />
            <span className="attn">
              <i style={{ width: `${Math.round(r.attention * 100)}%` }} />
            </span>
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
