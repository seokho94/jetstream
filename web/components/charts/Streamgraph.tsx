import { stack, stackOffsetWiggle, stackOrderInsideOut, area, curveBasis } from "d3-shape";
import { hueFor, type StreamgraphSeries } from "@jetstream/shared";

type Row = Record<string, number>;

// 6 currents over ~8 weeks, centered baseline (stream / "wiggle" offset).
export function Streamgraph({
  data,
  width = 420,
  height = 150,
}: {
  data: StreamgraphSeries[];
  width?: number;
  height?: number;
}) {
  const keys = data.map((s) => s.currentId);
  const T = data[0]?.series.length ?? 0;
  if (!T) return null;

  const rows: Row[] = Array.from({ length: T }, (_, i) => {
    const row: Row = {};
    data.forEach((s) => (row[s.currentId] = s.series[i]?.share ?? 0));
    return row;
  });

  const layers = stack<Row>().keys(keys).offset(stackOffsetWiggle).order(stackOrderInsideOut)(rows);

  let lo = Infinity;
  let hi = -Infinity;
  layers.forEach((layer) =>
    layer.forEach((p) => {
      lo = Math.min(lo, p[0]);
      hi = Math.max(hi, p[1]);
    })
  );
  const x = (i: number) => (i / (T - 1 || 1)) * width;
  const y = (v: number) => height - ((v - lo) / (hi - lo || 1)) * height;

  const ar = area<(typeof layers)[number][number]>()
    .x((_d, i) => x(i))
    .y0((d) => y(d[0]))
    .y1((d) => y(d[1]))
    .curve(curveBasis);

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="6개 흐름의 최근 8주 관심 추이">
      {layers.map((layer, li) => {
        const key = keys[li] ?? "other";
        return <path key={key} d={ar(layer) ?? ""} fill={hueFor(key)} opacity={0.85} />;
      })}
    </svg>
  );
}
