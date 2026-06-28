import { notFound } from "next/navigation";
import { getCurrent } from "@/lib/api";
import { hueFor } from "@jetstream/shared";
import { vars } from "@/lib/style";
import { MomentumBadge } from "@/components/MomentumBadge";
import { AttentionArc } from "@/components/charts/AttentionArc";

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

      <h3>Brief</h3>
      <p className="body">
        <b>무슨 일</b> — {cv.brief.whatsHappening}
      </p>
      <p className="body">
        <b>왜 중요</b> — {cv.brief.whyItMatters}
      </p>
      {cv.brief.citations.length > 0 && (
        <div className="cites">
          <span className="cites-label">근거</span>
          {Array.from(new Map(cv.brief.citations.map((c) => [c.url || c.outlet, c])).values()).map((c, i) => (
            <a key={i} className="cite" href={c.url || "#"} target="_blank" rel="noreferrer" title={c.text}>
              {c.outlet || "source"}
            </a>
          ))}
        </div>
      )}

      <h3>Timeline</h3>
      <ol className="timeline">
        {cv.timeline.map((n) => (
          <li key={n.node} className={n.isLatest ? "latest" : ""}>
            <span className="node-no">{n.node}</span>
            <div className="date">{n.date}</div>
            <div className="txt">{n.text}</div>
            <div className="src">{n.sources.map((s) => s.outlet).join(" · ")}</div>
          </li>
        ))}
      </ol>

      <h3>How it&apos;s being covered</h3>
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

      <div className="watch">
        <span>이 흐름이 움직일 때 알림</span>
        <span className="muted">Watch ○</span>
      </div>
    </div>
  );
}
