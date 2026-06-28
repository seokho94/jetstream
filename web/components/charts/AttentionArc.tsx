import { area, line, curveMonotoneX } from "d3-shape";
import type { ArcPoint } from "@meridian/shared";

// Attention over ~6 months with numbered event markers (1..5) that map to timeline nodes.
export function AttentionArc({
  points,
  color,
  width = 420,
  height = 170,
}: {
  points: ArcPoint[];
  color: string;
  width?: number;
  height?: number;
}) {
  const N = points.length;
  const x = (i: number) => (i / (N - 1 || 1)) * (width - 8) + 4;
  const y = (v: number) => height - 22 - v * (height - 44); // value is already 0..1
  const base = height - 22;

  const ar = area<ArcPoint>()
    .x((_d, i) => x(i))
    .y0(base)
    .y1((d) => y(d.value))
    .curve(curveMonotoneX);
  const ln = line<ArcPoint>()
    .x((_d, i) => x(i))
    .y((d) => y(d.value))
    .curve(curveMonotoneX);

  const markers = points.map((p, i) => ({ p, i })).filter((o) => o.p.marker);

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="이 흐름의 관심 추이와 주요 사건">
      <path d={ar(points) ?? ""} fill={color} opacity={0.16} />
      <path d={ln(points) ?? ""} fill="none" stroke={color} strokeWidth={2} />
      {markers.map(({ p, i }) => (
        <g key={p.marker}>
          <circle cx={x(i)} cy={y(p.value)} r={9} fill={color} />
          <text x={x(i)} y={y(p.value) + 3.6} textAnchor="middle" fontSize={11} fontWeight={700} fill="#0E1116">
            {p.marker}
          </text>
        </g>
      ))}
    </svg>
  );
}
