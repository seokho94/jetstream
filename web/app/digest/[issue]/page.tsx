import { getDigest } from "@/lib/api";
import { SlopeChart } from "@/components/charts/SlopeChart";

export default async function DigestPage({ params }: { params: { issue: string } }) {
  const d = await getDigest(Number(params.issue));
  return (
    <div className="digest">
      <header className="appbar">
        <div className="brand">
          <span className="dot" />
          Digest
        </div>
        <span className="asof">
          #{d.issue} · {d.weekOf}
        </span>
      </header>

      <p className="lede">{d.lede}</p>

      <p className="kicker" style={{ padding: "6px 18px 0" }}>
        이번 주 순위 변화 (지난주 → 이번주)
      </p>
      <div className="card">
        <SlopeChart rows={d.reshuffle} />
      </div>

      <div className="movers">
        <div className="mover up">
          <div className="dir">▲ 최대 상승</div>
          <div>{d.movers.climber.name}</div>
          <div className="muted">
            {d.movers.climber.lastRank}→{d.movers.climber.thisRank} · {d.movers.climber.note}
          </div>
        </div>
        <div className="mover down">
          <div className="dir">▼ 최대 하락</div>
          <div>{d.movers.faller.name}</div>
          <div className="muted">
            {d.movers.faller.lastRank}→{d.movers.faller.thisRank} · {d.movers.faller.note}
          </div>
        </div>
      </div>

      <p className="kicker" style={{ padding: "6px 18px 0" }}>
        무슨 일이 있었나
      </p>
      {d.blurbs.map((b, i) => (
        <div className="blurb" key={i}>
          <div className="kkr">{b.kicker}</div>
          <div>{b.body}</div>
        </div>
      ))}

      <p className="kicker" style={{ padding: "6px 18px 0" }}>
        다음 주 관전 포인트
      </p>
      <ul className="watch-next">
        {d.watchNext.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>

      <div className="stats">
        <div className="stat">
          <b>{d.stats.currentsTracked}</b>
          <span>추적 흐름</span>
        </div>
        <div className="stat">
          <b>{d.stats.newThreads}</b>
          <span>새 흐름</span>
        </div>
        <div className="stat">
          <b>{d.stats.storiesScanned.toLocaleString()}</b>
          <span>스캔 기사</span>
        </div>
      </div>
    </div>
  );
}
