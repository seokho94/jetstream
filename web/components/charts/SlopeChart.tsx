import { hueFor } from "@meridian/shared";

interface ReshuffleRow {
  currentId: string;
  name: string;
  colorKey: string;
  lastRank: number;
  thisRank: number;
}

// Last-week rank → this-week rank, lines colored by current (the digest's signature visual).
export function SlopeChart({
  rows,
  width = 420,
  height = 230,
}: {
  rows: ReshuffleRow[];
  width?: number;
  height?: number;
}) {
  const n = rows.length;
  const top = 24;
  const bottom = height - 14;
  const yFor = (rank: number) => top + ((rank - 1) / (n - 1 || 1)) * (bottom - top);
  const xl = 64;
  const xr = width - 150;

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="지난주 대비 이번주 순위 변화">
      <text x={xl} y={14} textAnchor="middle" fontSize={10} fill="#6B7480">지난주</text>
      <text x={xr} y={14} textAnchor="middle" fontSize={10} fill="#6B7480">이번주</text>
      {rows.map((r) => {
        const c = hueFor(r.colorKey);
        const y1 = yFor(r.lastRank);
        const y2 = yFor(r.thisRank);
        return (
          <g key={r.currentId}>
            <line x1={xl} y1={y1} x2={xr} y2={y2} stroke={c} strokeWidth={2} opacity={0.9} />
            <circle cx={xl} cy={y1} r={3.2} fill={c} />
            <circle cx={xr} cy={y2} r={3.2} fill={c} />
            <text x={xl - 9} y={y1 + 3.5} textAnchor="end" fontSize={10} fill={c}>{r.lastRank}</text>
            <text x={xr + 9} y={y2 + 3.5} textAnchor="start" fontSize={11} fill={c} fontWeight={700}>
              {r.thisRank}. {r.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
