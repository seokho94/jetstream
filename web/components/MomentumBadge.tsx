import { momentum, type MomentumState } from "@jetstream/shared";
import { vars } from "@/lib/style";

// Tabler outline icon paths (inline so the badge renders offline).
const ICON_PATHS: Record<string, string> = {
  "ti-trending-up": "M3 17l6 -6l4 4l8 -8 M14 7l7 0l0 7",
  "ti-activity": "M3 12h4l3 8l4 -16l3 8h4",
  "ti-trending-down": "M3 7l6 6l4 -4l8 8 M14 17l7 0l0 -7",
  "ti-minus": "M5 12l14 0",
};

// Momentum is encoded with color + icon + label (never color alone — CANON §2).
export function MomentumBadge({ state }: { state: MomentumState }) {
  const m = momentum[state];
  return (
    <span className="badge" style={vars({ "--c": m.hex })}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d={ICON_PATHS[m.icon]} />
      </svg>
      {m.labelEn}
    </span>
  );
}
