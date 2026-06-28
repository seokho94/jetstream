import { notFound } from "next/navigation";
import { getCurrent } from "@/lib/api";
import { hueFor } from "@jetstream/shared";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";
import { AttentionArc } from "@/components/charts/AttentionArc";
import { WatchToggle } from "@/components/WatchToggle";

const COVER_FILLS = [
  "var(--c)",
  "color-mix(in srgb, var(--c) 55%, var(--card))",
  "color-mix(in srgb, var(--c) 28%, var(--card))",
];

export default async function CurrentPage({ params }: { params: { id: string } }) {
  const cv = await getCurrent(params.id);
  if (!cv) notFound();
  const c = hueFor(cv.colorKey);

  return (
    <div className="detail" style={vars({ "--c": c })}>
      <div className="band">
        <div className="eyebrow">{cv.colorKey}</div>
        <div className="title">{cv.name}</div>
        <MomentumBadge state={cv.state} />
      </div>

      <AttentionArc points={cv.arc} color={c} />
      <p className="micro">아크 위 번호 = 아래 타임라인의 같은 번호 사건</p>

      <h3>브리핑</h3>
      <p className="body">
        <b>What?</b> — {cv.brief.whatsHappening}
      </p>
      <p className="body">
        <b>Why?</b> — {cv.brief.whyItMatters}
      </p>
      {cv.brief.citations.length > 0 && (
        <div className="srcs">
          <div className="srcs-head">
            출처 {new Set(cv.brief.citations.map((c) => c.url || c.outlet)).size}곳 · 인용 {cv.brief.citations.length}건
          </div>
          <ul>
            {cv.brief.citations.map((c, i) => (
              <li key={i}>
                <a className="src-outlet" href={c.url || "#"} target="_blank" rel="noreferrer">
                  {c.outlet || "source"} ↗
                </a>
                {c.text && <span className="src-quote">“{c.text.slice(0, 140)}”</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <h3>타임라인</h3>
      <ol className="timeline">
        {cv.timeline.map((n) => (
          <li key={n.node} className={n.isLatest ? "latest" : ""}>
            <span className="node-no">{n.node}</span>
            <div className="date">{n.date}</div>
            <div className="txt">{n.text}</div>
            <div className="src">
              {n.sources
                .filter((s) => s.outlet)
                .map((s, i) => (
                  <span key={i}>
                    {i > 0 && " · "}
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noreferrer" title={s.text || undefined}>
                        {s.outlet}
                      </a>
                    ) : (
                      s.outlet
                    )}
                  </span>
                ))}
            </div>
          </li>
        ))}
      </ol>

      <h3>어떻게 다뤄지나</h3>
      <p className="micro">지역별 보도 분포 — 특정 지역에 치우치지 않는지 보여줍니다</p>
      <div className="coverage">
        {cv.coverage.buckets.map((b, i) => (
          <span key={b.label} style={{ width: `${b.pct}%`, background: COVER_FILLS[i % COVER_FILLS.length] }} />
        ))}
      </div>
      <div className="cov-legend">
        {cv.coverage.buckets.map((b) => (
          <span key={b.label}>
            {b.label} {b.pct}%
          </span>
        ))}
      </div>

      <div style={{ margin: "22px 18px" }}>
        <WatchToggle currentId={cv.currentId} />
      </div>
    </div>
  );
}
