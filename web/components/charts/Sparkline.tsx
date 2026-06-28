import { line, curveMonotoneX } from "d3-shape";

export function Sparkline({
  data,
  color,
  width = 64,
  height = 22,
}: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const x = (i: number) => (i / (data.length - 1 || 1)) * (width - 2) + 1;
  const y = (v: number) => height - 2 - ((v - min) / (max - min || 1)) * (height - 4);
  const gen = line<number>()
    .x((_d, i) => x(i))
    .y((d) => y(d))
    .curve(curveMonotoneX);
  return (
    <svg className="spark" width={width} height={height} aria-hidden>
      <path d={gen(data) ?? ""} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />
    </svg>
  );
}
